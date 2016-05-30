# ec2_route53_sync.utils

from collections import defaultdict


def apply_rr_diff(resource_records, ip_changes):
    ip_addresses = set(rec['Value'] for rec in resource_records)
    if 'to_add' in ip_changes:
        ip_addresses = ip_addresses.union(ip_changes['to_add'])
    if 'to_prune' in ip_changes:
        ip_addresses = ip_addresses.difference(ip_changes['to_prune'])
    return [{'Value': ip_addr} for ip_addr in ip_addresses]


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


def get_instance_tag(tag_name, instance, name_is_fqdn=False):
    for tag in instance.tags:
        if tag['Key'] == tag_name:
            return tag['Value'] if not name_is_fqdn else tag['Value'].split('.')[0]
    raise KeyError(tag_name)
