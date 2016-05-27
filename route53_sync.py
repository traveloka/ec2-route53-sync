import boto3
import click
from collections import defaultdict

ec2_client = boto3.client('ec2')
r53_client = boto3.client('route53')
ec2 = boto3.resource('ec2')


class HostIP(object):
    def __init__(self, hostname, ip_address=None):
        self.hostname = hostname
        self.ip_address = ip_address

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.hostname == other.hostname \
               and self.ip_address == other.ip_address

    def __hash__(self):
        return hash((self.hostname, self.ip_address))

    def __repr__(self):
        return "HostIP({}, ip_address={})"\
            .format(repr(self.hostname),
                    repr(self.ip_address))


def get_instance_tag(tag_name, instance, name_is_fqdn=False):
    for tag in instance.tags:
        if tag['Key'] == tag_name:
            return tag['Value'] if not name_is_fqdn else tag['Value'].split('.')[0]
    raise KeyError(tag_name)


def get_ec2_hosts(vpc_ids=[], hostname_tag='Name', name_is_fqdn=False, include_ec2=False):
    instances_it = ec2.instances.filter(
        Filters=[
            {'Name': 'tag-key',
             'Values': [hostname_tag]},
            {'Name': 'instance-state-code',
             'Values': ['16']}
        ]
    )
    return set(HostIP(get_instance_tag(hostname_tag, i, name_is_fqdn),
                      i.private_ip_address)
               for i in instances_it
               if i.vpc_id in vpc_ids or (include_ec2 and not i.vpc_id))


def get_zone_records(zone_id):
    a_records = []
    rrs = r53_client.list_resource_record_sets(HostedZoneId=zone_id)
    while True:
        a_records += [r for r in rrs['ResourceRecordSets']
                      if r['Type'] == 'A']
        if not rrs['IsTruncated']:
            break
        rrs = r53_client.list_resource_record_sets(HostedZoneId=zone_id, StartRecordName=rrs['NextRecordName'])

    return set(HostIP(r['Name'].split('.')[0], rr['Value'])
               for r in a_records
               for rr in r['ResourceRecords']),\
           a_records


def get_tag_zone_diff(hostname_tag,
                      zone_id,
                      name_is_fqdn,
                      include_ec2,
                      vpc_ids):
    hosts_from_tag = get_ec2_hosts(vpc_ids, hostname_tag, name_is_fqdn, include_ec2)
    hosts_from_zone, a_records = get_zone_records(zone_id)
    hosts_to_add = hosts_from_tag - hosts_from_zone
    hosts_to_prune = hosts_from_zone - hosts_from_tag
    return hosts_to_add, hosts_to_prune, a_records


def create_merged_diff(hosts_to_add, hosts_to_prune):
    d_to_add = defaultdict(set)
    d_to_prune = defaultdict(set)
    d_to_change = defaultdict(dict)
    for h in hosts_to_add:
        d_to_add[h.hostname].add(h.ip_address)
    for h in hosts_to_prune:
        d_to_prune[h.hostname].add(h.ip_address)
    for hostname in d_to_add.keys():
        d_to_change[hostname]['to_add'] = d_to_add[hostname]
    for hostname in d_to_prune.keys():
        d_to_change[hostname]['to_prune'] = d_to_prune[hostname]
    return d_to_change


def apply_rr_diff(resource_records, ip_changes):
    ip_addresses = set(rec['Value'] for rec in resource_records)
    if 'to_add' in ip_changes:
        ip_addresses = ip_addresses.union(ip_changes['to_add'])
    if 'to_prune' in ip_changes:
        ip_addresses = ip_addresses.difference(ip_changes['to_prune'])
    return [{'Value': ip_addr} for ip_addr in ip_addresses]


def create_zone_changes(zone_diff, a_records, zone_name):
    a_rec_dict = dict()
    for a_rec in a_records:
        hostname = a_rec['Name'].split('.')[0]
        a_rec_dict[hostname] = a_rec

    changes = []
    zone_diff_hosts = set(zone_diff.keys())
    a_rec_hosts = set(a_rec_dict.keys())
    # hosts already in the zone, to delete or upsert
    for hostname in zone_diff_hosts.intersection(a_rec_hosts):
        ip_changes = zone_diff[hostname]
        new_resource_records = apply_rr_diff(a_rec_dict[hostname]['ResourceRecords'], ip_changes)
        print("Host: {} -- new IPs: {}".format(hostname, new_resource_records))
        new_a_rec = a_rec_dict[hostname].copy()
        if not new_resource_records:
            action = 'DELETE'
        else:
            action = 'UPSERT'
            new_a_rec['ResourceRecords'] = new_resource_records
        changes.append({'Action': action, 'ResourceRecordSet': new_a_rec})
    # hosts not in the zone yet
    for hostname in zone_diff_hosts.difference(a_rec_hosts):
        changes.append({
            'Action': 'CREATE',
            'ResourceRecordSet':
                create_resource_record_set(
                    hostname
                    , zone_name
                    , zone_diff[hostname]['to_add']
                )})
    return changes


def apply_zone_changes(zone_id, changes, batch_size=100):
    changes_size = len(changes)
    for i in range(0, changes_size, batch_size):
        change_batch = changes[i:min(i+batch_size, changes_size)]
        print("changes[{}:{}]: {}".format(i, min(i+batch_size, changes_size), change_batch[0]))
        r53_client.change_resource_record_sets(HostedZoneId=zone_id, ChangeBatch={'Changes': change_batch})


def create_resource_record_set(hostname, zone_name, ip_addresses, ttl=300):
    """ Creates a resource record set
    :param hostname:
    :param zone_name:
    :param ip_addresses:
    :return: dictionary containing resource record set

    >>> create_resource_record_set('foo', 'bar.baz', ['1.2.3.4', '5.6.7.8']) == { \
      'Name': "foo.bar.baz.", 'Type': 'A', 'TTL': 300, \
      'ResourceRecords': [{'Value': '1.2.3.4'}, {'Value': '5.6.7.8'}]}
    True
    """
    return {
        'Name': "{}.{}.".format(hostname, zone_name),
        'Type': 'A',
        'TTL': ttl,
        'ResourceRecords': [{'Value': ip_addr}
                            for ip_addr in ip_addresses]
    }

@click.command()
@click.option('--tag', default='Name', help='The tag containing instance host names')
@click.option('--fqdn/--no-fqdn', default=False, help='Is the name FQDN or the hostname portion only')
@click.option('--include-ec2/--exclude-ec2', default=False)
@click.option('--vpc-id', multiple=True)
@click.argument('zone_id')
@click.argument('zone_name')
def sync_tag_with_zone(
        tag,
        fqdn,
        zone_id,
        zone_name,
        include_ec2,
        vpc_id
        ):
    if not zone_id.startswith("/hostedzone/"):
        zone_id = "/hostedzone/{}".format(zone_id)
    hosts_to_add, hosts_to_prune, a_records = get_tag_zone_diff(tag, zone_id, fqdn, include_ec2, vpc_id)
    zone_diff = create_merged_diff(hosts_to_add, hosts_to_prune)
    changes = create_zone_changes(zone_diff, a_records, zone_name)
    apply_zone_changes(zone_id, changes)


def test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    test()
    sync_tag_with_zone()
