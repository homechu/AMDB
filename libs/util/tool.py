from datetime import datetime
import ipaddress, re
import ipaddress


def is_valid_ip(data):
    try:
        ipaddress.ip_address(data)
    except ValueError:
        return False
    return True


def is_valid_ipv4(data):
    try:
        ipaddress.IPv4Address(data)
    except ValueError:
        return False
    return True


def is_valid_cname(data):
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*(\.[a-zA-Z]{2,})$'
    return re.match(pattern, data) is not None


def is_valid_datetime(date_string, format_string="%Y-%m-%d %H:%M:%S"):
    try:
        datetime.strptime(date_string, format_string)
    except ValueError:
        return False
    return True


def cidr_to_ip_range(cidr):
    '''
    輸入參數cidr = '192.168.1.0/24'
    返回值為: 子網掩碼, 所有IP地址範圍, 除去網絡地址和廣播地址的IP地址範圍
    '''
    net = ipaddress.ip_network(cidr, strict=False)

    ip_range = []
    for ip in net:
        ip_range.append(ip.__str__())

    host_range = []
    for host in net.hosts():
        host_range.append(host.__str__())

    return net.netmask.__str__(), ip_range, host_range


if __name__ == "__main__":
    mask, ip_range, host_range = cidr_to_ip_range("1.2.3.15/28")
    print(mask)
    print(ip_range)
    print(host_range)
