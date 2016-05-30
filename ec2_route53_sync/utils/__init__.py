# ec2_route53_sync.utils

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
