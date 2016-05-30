# ec2_route53_sync.models


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
