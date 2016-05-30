import boto3
import click
from ec2_route53_sync.utils import (
    create_merged_diff,
    create_zone_changes,
    get_instance_tag,
)

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


def apply_zone_changes(zone_id, changes, batch_size=100):
    changes_size = len(changes)
    for i in range(0, changes_size, batch_size):
        change_batch = changes[i:min(i+batch_size, changes_size)]
        print("changes[{}:{}]: {}".format(i, min(i+batch_size, changes_size), change_batch[0]))
        r53_client.change_resource_record_sets(HostedZoneId=zone_id, ChangeBatch={'Changes': change_batch})


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
