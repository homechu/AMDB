from .base import Terraform
from shutil import copyfile
import os
import json

import ipaddress


class Create(Terraform):
    valid_text = "add"
    command = "terraform apply -no-color -auto-approve"

    def run(self):
        self.create_host_dir()
        self.data(self.vars)
        self.copyfile()
        self._init()
        self._plan()
        self._main()

    def data(self, vars):
        js = os.path.join(self.path['conf'], 'terraform_example.tfvars.json')
        data = json.load(open(js, 'r'))

        data.update(vars)

        # data['hostname'] = self.hostname
        # data['ipaddress'] = self.ipaddress
        tfvars_json = open(os.path.join(self.path['host'], 'terraform.tfvars.json'), 'w')
        json.dump(data, tfvars_json)
        tfvars_json.close()

    def copyfile(self):
        for file in ['main.tf', 'variables.tf']:
            copyfile(os.path.join(self.path['conf'], file), os.path.join(self.path['host'], file))


class CustomIPCreate(Create):
    dhcp = False

    def get_vars(self, ip, net_mapping_data):
        """

        :param ip: 192.168.1.1
        :param net_mapping_data:
            [
                {
                    "lan": "192.168.1.0/24",
                    "network": "VLAN13",
                    "gateway": "192.168.1.254"
                }
            ]
        :return:
        """

        for net_data in net_mapping_data:
            if ipaddress.IPv4Address(ip) in ipaddress.ip_network(net_data['lan'], strict=False):
                return {
                    'network': net_data['network'],
                    'gateway': net_data['gateway']
                }


    def __init__(self, **kwargs):
        self.vars = kwargs

        net_mapping_data = self.vars.get('net_mapping_data')
        ipaddress = self.vars.get('ipaddress')
        if ipaddress and net_mapping_data:
            net_vars = self.get_vars(ipaddress,net_mapping_data)
            self.vars.update(net_vars)

        super(CustomIPCreate, self).__init__(**kwargs)