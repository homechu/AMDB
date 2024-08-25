import hashlib
import json
import traceback

from collections import defaultdict
from urllib.parse import urlparse

from django.core.cache import cache
from requests.exceptions import Timeout
from selfpackage.django.utils.http import HTTPClient

from apps.cmdb.models.idc import IDC
from apps.cmdb.models.virtual import VCenterInfo
from apps.openstacks.exceptions import OpenstackAPIException, OpenstackAPILoginException
from libs import tool
from libs.base.fields import SecureCryptField
from main.settings import logger


class OpenStack(HTTPClient):
    client_verify = False
    error_acc = None
    resp = None
    _projects = []

    def __init__(self, host=None, include_interface: str = 'public'):
        self.identity_url = f'{host}:5000/v3'
        self.header = {'Content-Type': 'application/json'}
        self.result = tool.Result()
        self.region = defaultdict(lambda: dict())
        self.include_interface = include_interface
        self.user_domain_name = 'default'
        self.project_domain_name = 'default'
        self.exclude_project = ['admin', 'service']
        self.cont_timeout = 5.0
        self.read_timeout = 60.0

    @classmethod
    def from_idc(cls, idc: IDC, project_id: str = '') -> 'OpenStack':
        vc: VCenterInfo = idc.vcenterinfo
        sc = SecureCryptField()
        _cls = cls(idc.domain)
        key = 'openstack:' + hashlib.md5(f'{idc.id}-{project_id}'.encode()).hexdigest()
        if not cache.has_key(key):
            res = _cls._login(vc.openstack_admin_user, vc.openstack_admin_pass, project_id)
            if not res.OK:
                raise OpenstackAPILoginException(res.data)

            res = _cls.projects()
            if not res.OK:
                raise OpenstackAPIException(res.data)

            kw = {'header': _cls.header, 'region': _cls.region, '_projects': _cls._projects}
            c = sc.encrypt(json.dumps(kw))
            cache.set(key, c, 300)
        else:
            for k, v in json.loads(sc.decrypt(cache.get(key).decode())).items():
                setattr(_cls, k, v)

        return _cls

    def get_url(self, region, type_, path):
        """
        根據region, type_, path獲取接口地址
        -----
        Parameters:
            region(str): 機房名稱
            type_(str): 接口類型
            path(str): 目標路徑
        """
        try:
            url = self.region[str(region)][type_]['url']
            if type_ == 'network':
                url += f'/v2.0{path}'
            elif type_ == 'compute':
                url += f'/v2.1{path}'
            elif type_ == 'volumev3':
                url += f'/v3{path}'
            elif type_ == 'image':
                url += f'/v2{path}'

            self.result.set(url)
        except Exception:
            self.result.set(traceback.format_exc(), False)
            return self.result
        return self.result

    def login(self, admin: dict, user: dict, project: str = '', user_login: bool = False):
        """
        登入後獲取資訊
        -----
        Parameters:
            admin: 預設管理員
            user: 使用者
            project: 項目名稱
        -----
        Return: {OK(bool), line(str), data(any)}
        """
        # 預設管理員登入
        result = self._login(admin['user'], admin['password'], admin['project_id'])
        if not result.OK:
            self.error_acc = admin['user']
            return result

        # 獲取項目列表
        pr_res = self.projects()
        if not pr_res.OK:
            logger.error(f'Projects Error\nUser:{admin["user"]}\nResponse:{pr_res.data}')

        if not user_login:
            return result

        # 指定項目ID，用於操作不同項目
        if project:
            pro_map = {k.upper(): v for k, v in self._projects.items()}
            user['project_id'] = pro_map.get(project.upper())
            if not user['project_id']:
                self.result.set(f'查無 {project} 項目', False)
                return self.result
        else:
            logger.info('login without project')

        # 預設使用者登入
        result = self._login(user['user'], user['password'], user['project_id'])
        if not result.OK:
            self.error_acc = user['user']
            return result

        return result

    def _login(self, user, password, project_id: str = ''):
        """
        登入接口：
        -----
        Parameters:
            user(str): 用户名
            password(str): 密碼
            id_(str): admin project ID
            project(str): 項目名稱
        -----
        Return: {OK(bool), line(str), data(any)}
        """
        self.username = user
        self.password = password

        path = '/auth/tokens'
        url = self.identity_url + path
        body = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'name': user,
                            'domain': {'name': self.user_domain_name},
                            'password': password,
                        }
                    },
                }
            }
        }

        # Project-Scoped with Project ID
        if project_id:
            body['auth']['scope'] = {'project': {'id': project_id}}

        result = self._post(url, body)
        if not result.OK:
            logger.error(f'{user} login error at {url} {result.data}')
            return result

        # self.header = self.resp.headers
        self.header['X-Auth-Token'] = self.resp.headers['X-Subject-Token']

        # Get Region, Catalog
        data = result.data
        if not project_id and 'catalog' not in data['token']:
            logger.info(f"{user} login with no scope")
            return self.result

        for catalog in data['token']['catalog']:
            for endpoint in catalog['endpoints']:
                # Conditions for interface and region
                if endpoint['interface'] in self.include_interface:
                    o = urlparse(endpoint['url'])
                    self.region[endpoint['region'].upper()][catalog['type']] = {
                        'region': endpoint['region'],
                        'type': catalog['type'],
                        'interface': endpoint['interface'],
                        'url': f'{o.scheme}://{o.netloc}',
                    }

        return self.result

    def _get(self, url, params=dict()):
        """
        通用Get方法
        """
        try:
            logger.debug(f'GET {url} {params}')
            self.resp = self.http_client.get(
                url,
                params=params,
                headers=self.header,
                timeout=(self.cont_timeout, self.read_timeout),
            )

            resp = self.resp
            if resp.status_code != 200:
                if 'itemNotFound' in resp.text:
                    logger.warning(f'{url} {resp.text}')
                else:
                    logger.error(f'{url} {resp.text}')
                self.result.set(resp.text, False)
                return self.result

            self.result.set(resp.json() if resp.text else '')
        except Timeout as e:
            logger.warning(f'{url} {self.resp.text if self.resp else None} {e}')
            self.result.set(f'{url} Timeout', False)

        except Exception as e:
            logger.error(f'{url} {self.resp.text if self.resp else None} {e}')
            self.result.set(str(e), False)

        return self.result

    def _post(self, url, body):
        """
        通用Post方法
        """
        try:
            self.resp = self.http_client.post(
                url, json=body, headers=self.header, timeout=(self.cont_timeout, self.read_timeout)
            )

            resp = self.resp
            if resp.status_code not in [200, 201, 202, 204]:
                logger.error(f'{url} {resp.text}')
                self.result.set(resp.text, False)
                return self.result

            self.result.set(resp.json() if resp.text else '')
        except Exception as e:
            logger.error(f'{url} {self.resp.text if self.resp else None} {e}')
            self.result.set(str(e), False)

        return self.result

    def _put(self, url, body):
        """
        通用Put方法
        """
        try:
            self.resp = self.http_client.put(url, json=body, headers=self.header)
            resp = self.resp
            if resp.status_code not in [200, 201, 202, 204]:
                logger.error(f'{url} {resp.text}')
                self.result.set(resp.text, False)
                return self.result

            self.result.set(resp.json() if resp.text else '')
        except Exception as e:
            logger.error(f'{url} {self.resp.text if self.resp else None} {e}')
            self.result.set(str(e), False)

        return self.result

    def _delete(self, url):
        """
        通用Delete方法
        """
        try:
            self.resp = self.http_client.delete(url, headers=self.header)
            resp = self.resp
            if resp.status_code not in [200, 201, 202, 204]:
                logger.error(f'{url} {resp.text}')
                self.result.set(resp.text, False)
                return self.result

            self.result.set(resp.json() if resp.text else '')
        except Exception as e:
            logger.error(f'{url} {self.resp.text if self.resp else None} {e}')
            self.result.set(str(e), False)
        return self.result

    def auth_projects(self):
        """
        獲取賬號項目權限
        """
        path = '/auth/projects'
        url = self.identity_url + path
        return self._get(url)

    def projects(self):
        """
        獲取project列表
        """
        path = '/projects'
        url = self.identity_url + path
        result = self._get(url)
        if result.OK:
            self._projects = {n['name']: n['id'] for n in result.data['projects']}

        return result

    def create_project(self, project):
        """創建 project"""

        body = {'project': {'name': project}}
        return self._post(self.identity_url + '/projects', body)

    def attach_role(self, project_id, group_id, role_id, **kwargs):
        """創建 project"""

        path = f'/projects/{project_id}/groups/{group_id}/roles/{role_id}'
        return self._put(self.identity_url + path, kwargs)

    def attach_user_role_project(self, project_id, user_id, role_id):
        """創建 project"""

        path = f'/projects/{project_id}/users/{user_id}/roles/{role_id}'
        return self._put(self.identity_url + path, {})

    def images(self, region):
        """鏡像列表明細.

        Parameters:
            region(str): 機房名稱

        Returns: dict['images'][item|list]: 鏡像列表.

        Items:
            {
                "container_format": "bare",
                "min_ram": 512,
                "locations": [],
                "hw_scsi_model": "virtio-scsi",
                "file": "/v2/images/a98540fd-0456-43e5-9c85-3f6b0f45e4a9/file",
                "owner": "316dc554f345440e857025a4fe21b938",
                "id": "a98540fd-0456-43e5-9c85-3f6b0f45e4a9",
                "size": 8589934592,
                "os_distro": "centos7.0",
                "self": "/v2/images/a98540fd-0456-43e5-9c85-3f6b0f45e4a9",
                "disk_format": "raw",
                "os_hash_algo": "sha512",
                "os_version": "7.0",
                "hw_vif_multiqueue_enabled": "true",
                "hw_disk_bus": "scsi",
                "schema": "/v2/schemas/image",
                "status": "active",
                "description": "CentOS-7-x86_64-GenericCloud-1907",
                "tags": [],
                "hw_qemu_guest_agent": "yes",
                "visibility": "private",
                "updated_at": "2021-08-15T10:11:54Z",
                "min_disk": 8,
                "virtual_size": null,
                "name": "CentOS-7.6-x86_64-1907",
                "os_require_quiesce": "yes",
                "checksum": "06e9262ab9e9f3dcf4db97a1892f58f0",
                "created_at": "2019-11-13T04:41:30Z",
                "hw_vif_model": "virtio",
                "os_hidden": false,
                "protected": true,
                "architecture": "x86_64",
                "os_hash_value": ""
            }
        """
        path = '/images'
        url = self.get_url(region, 'image', path)
        return self._get(url)

    def flavors(self, region: str):
        """套餐列表明細.

        Parameters:
            region(str): 機房名稱.

        Returns: dict['flavors'][item|list]: 套餐列表.

        Items:
            {
                "links": [],
                "ram": 16384,
                "OS-FLV-DISABLED:disabled": false,
                "os-flavor-access:is_public": true,
                "rxtx_factor": 1.0,
                "disk": 200,
                "id": "e83b0f29-1fde-4fc3-9c34-eb311205f68a",
                "name": "16U16G-200GB",
                "vcpus": 16,
                "swap": "",
                "OS-FLV-EXT-DATA:ephemeral": 0
            }
        """
        path = '/flavors/detail'
        url = self.get_url(region, 'compute', path)
        return self._get(url)

    def volume_types(self, region, *args, **kwargs):
        """卷類型.

        Parameters:
            region(str): 機房名稱.

        Returns: dict['volume_types'][item|list]: 卷類型列表.

        Items:
            {
                "name": "High",
                "qos_specs_id": "87f4fbac-f05a-4dfb-af71",
                "extra_specs": {},
                "os-volume-type-access:is_public": true,
                "is_public": true,
                "id": "0c1aa0ae-4ad1-4765-83fb",
                "description": "5000 read io/s, 5000 write io/s"
            }
        """
        path = f"/{self._projects['admin']}/types"
        url = self.get_url(region, 'volumev3', path)
        return self._get(url)

    def volumes_attachments(self, region, *args, **kwargs):
        """卷綁定數據.

        Parameters:
            region(str): 機房名稱.

        """
        path = f"/{self._projects['admin']}/attachments/detail"
        url = self.get_url(region, 'volumev3', path)
        return self._get(url, dict(all_tenants=True, **kwargs))

    def volumes(self, region, *args, **kwargs):
        """卷列表

        Parameters:
            region(str): 機房名稱.
            project(str): 項目名稱.

        Returns: dict['volumes'][item|list]: 套餐列表.

        Items:
        {
            "migration_status": null,
            "attachments": [
                {
                    'server_id': '6c8cf6e0-4c8f-442f-9196-9679737feec6',
                    'attachment_id': '3dafcac4-1cb9-4b60-a227-d729baa10cf6',
                    'attached_at': '2019-09-30T19:30:34.000000',
                    'host_name': null,
                    'volume_id': '5d95d5ee-4bdd-4452-b9d7-d44ca10d3d53',
                    'device': '/dev/vda',
                    'id': '5d95d5ee-4bdd-4452-b9d7-d44ca10d3d53'
                }
            ],
            "links": [],
            "availability_zone": "nova",
            "os-vol-host-attr:host": "rbd:volumes@rbd-az1#rbd-az1",
            "encrypted": false,
            "updated_at": "2023-10-09T03:39:37.000000",
            "replication_status": null,
            "snapshot_id": null,
            "id": "28bb9d5c-3672-4e33-bdcc",
            "size": 200,
            "user_id": "71bbe4d0aa1a4407bd5",
            "os-vol-tenant-attr:tenant_id": "316dc554f3",
            "os-vol-mig-status-attr:migstat": null,
            "metadata": {},
            "status": "available",
            "volume_image_metadata": {
                "description": "CentOS-6-x86_64-GenericCloud-1907",
                "container_format": "bare",
                "hw_qemu_guest_agent": "yes",
                "image_name": "CentOS-6.10-x86_64-1907",
                "hw_scsi_model": "virtio-scsi",
                "image_id": "80ceea9e-8f8d-485b-b0b5",
                "min_ram": "512",
                "min_disk": "8",
                "size": "8589934592",
                "os_distro": "centos6.10",
                "os_require_quiesce": "yes",
                "checksum": "def080147d7e7d0b9",
                "hw_vif_model": "virtio",
                "disk_format": "raw",
                "os_version": "6.10",
                "architecture": "x86_64",
                "hw_vif_multiqueue_enabled": "true",
                "hw_disk_bus": "scsi"
            },
            "description": "",
            "multiattach": false,
            "source_volid": null,
            "consistencygroup_id": null,
            "os-vol-mig-status-attr:name_id": null,
            "name": "",
            "bootable": "true",
            "created_at": "2023-10-09T03:39:31.000000",
            "volume_type": null
        }
        """

        path = f"/{self._projects['admin']}/volumes/detail"
        url = self.get_url(region, 'volumev3', path)
        return self._get(url, dict(all_tenants=True, **kwargs))

    def add_volumes(self, region, project, size, volume_type='Normal', description='', name=''):
        """
        增加捲
        -----
        Parameters:
            region(str): 機房名稱
            project(str): 項目名稱
            volume_type(str): 磁盤類型
            size(int): 容量
            description(str): 描述
        """
        proejct_id = self._projects[str(project)]
        path = f'/{proejct_id}/volumes'
        url = self.get_url(region, 'volumev3', path)
        body = {
            'volume': {
                'size': int(size),
                'volume_type': volume_type,
                'description': description,
            }
        }
        if name:
            body['volume']['name'] = name

        logger.debug(f'{url}, {body}')
        return self._post(url, body)

    def put_volumes(self, region, project, id_, size='', description='', metadata={}):
        """
        修改卷
        -----
        Parameters:
            region(str): 機房名稱
            project(str): 項目名稱
            id_(str): 卷ID
            size(int): 容量
            description(str): 描述
            metatdata(dict): 元數據
        """
        proejct_id = self._projects[project]
        path = f'/{proejct_id}/volumes/{id_}'
        result = self.get_url(region, 'volumev3', path)
        if not result.OK:
            return result
        url = result.data
        body = {'volume': {}}
        if size:
            body['volume']['size'] = int(size)
        if description:
            body['volume']['description'] = description
        if metadata:
            body['volume']['metadata'] = metadata
        return self._put(url, body)

    def del_volumes(self, region, project, id_):
        """
        刪除卷
        -----
        Parameters:
            region(str): 機房名稱
            project(str): 項目名稱
            id_(str): 卷ID
        """
        proejct_id = self._projects[str(project)]
        path = f'/{proejct_id}/volumes/{id_}'
        url = self.get_url(region, 'volumev3', path)
        return self._delete(url)

    def os_volumes(self, region):
        """
        卷列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-volumes'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def add_os_volumes(self, region, size, name='', volume_type='', description=''):
        """
        卷列表
        -----
        Parameters:
            region(str): 機房名稱
            size(int): 容量
            name(str): 卷名稱
            volume_type(str): 卷類型
            description(str): 描述
        """
        path = '/os-volumes'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'volume': {
                'display_name': name,
                'display_description': description,
                'volume_type': volume_type,
                'size': int(size),
            }
        }
        return self._post(url, body)

    def put_os_volumes(self, region, size='', name='', description='', metadata={}):
        """
        卷列表
        -----
        Parameters:
            region(str): 機房名稱
            size(int): 容量
            name(str): 卷名稱
            description(str): 描述
            metadata(dict): 元數據
        """
        path = '/os-volumes'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'volume': {"display_name": name, "display_description": description, "size": int(size)}
        }
        return self._post(url, body)

    def server_os_volume_attachments(self, region, server_id):
        """
        服務器綁定卷列表
        -----
        Parameters:
            region(str): 機房名稱
            server_id(str): 服務器ID
        """
        path = f'/servers/{server_id}/os-volume_attachments'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def add_server_os_volume_attachments(self, region, server_id, volume_id):
        """
        服務器綁定卷
        -----
        Parameters:
            region(str): 機房名稱
            server_id(str): 服務器ID
            volume_id(str): 卷ID
        """
        path = f'/servers/{server_id}/os-volume_attachments'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'volumeAttachment': {
                'volumeId': volume_id,
            }
        }
        return self._post(url, body)

    def del_server_os_volume_attachments(self, region, server_id, volume_id):
        """
        服務器解除綁定卷
        -----
        Parameters:
            region(str): 機房名稱
            server_id(str): 服務器ID
            volume_id(str): 卷ID
        """
        path = f'/servers/{server_id}/os-volume_attachments/{volume_id}'
        url = self.get_url(region, 'compute', path)
        return self._delete(url)

    def os_keypairs(self, region):
        """
        密鑰列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-keypairs'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def servers_detail(self, region, *args, **kwargs):
        """
        服務器列表明細
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/servers/detail'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result

        url = result.data
        return self._get(url, dict(all_tenants=True, **kwargs))

    def os_networks(self, region):
        """網路列表
            os-networks DEPRECATED in Openstack 21.0.0
        -----
        Parameters:
            region(str): 機房名稱

        """
        path = '/os-networks'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def subnets(self, region):
        """
        子網路列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/subnets'
        url = self.get_url(region, 'network', path)
        return self._get(url)

    def os_server_groups(self, region, **kwargs):
        """
        服務器組列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-server-groups'
        url = self.get_url(region, 'compute', path)
        return self._get(url, kwargs)

    def add_os_server_groups(self, region, name):
        """
        添加服務器組列表
        -----
        Parameters:
            region(str): 機房名稱
            name(str): 組名
        """
        path = '/os-server-groups'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        self.header['OpenStack-API-Version'] = 'compute 2.27'
        body = {
            'server_group': {
                'name': name,
                'policies': ['soft-anti-affinity'],
            }
        }
        return self._post(url, body)

    def delete_os_server_groups(self, region, server_group_id):
        """
        刪除服務器組列表
        -----
        Parameters:
            region(str): 機房名稱.
            server_group_id(str): 組ID.
        """
        path = f'/os-server-groups/{server_group_id}'
        url = self.get_url(region, 'compute', path)
        return self._delete(url)

    def os_security_groups(self, region):
        """
        安全組列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-security-groups'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def os_availability_zone(self, region):
        """
        可用區列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-availability-zone'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def os_availability_zone_detail(self, region):
        """
        可用區列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-availability-zone/detail'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def os_hypervisors_detail(self, region):
        """
        可用區列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/os-hypervisors/detail'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def security_groups(self, region, *args, **kwargs):
        """
        安全組列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/security-groups'
        url = self.get_url(region, 'network', path)
        return self._get(url, kwargs)

    def security_groups_by_id(self, region, id_):
        """
        查詢單一安全組
        -----
        Parameters:
            region(str): 機房名稱
            id_(str): 安全組ID
        """
        path = '/security-groups/{}'.format(id_)
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def add_security_groups(self, region, name, description):
        """
        增加安全組
        -----
        Parameters:
            region(str): 機房名稱
            name(str): 安全組名稱
            description: 描述
        """
        path = '/security-groups'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'security_group': {
                'name': name,
                'description': description,
            }
        }
        return self._post(url, body)

    def put_security_groups(self, region, id_, name, description=''):
        """
        修改安全組
        -----
        Parameters:
            region(str): 機房名稱
            id_(str): 安全組ID
            name(str): 安全組名稱
            description: 描述
        """
        path = '/security-groups/{}'.format(id_)
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'security_group': {
                'name': name,
                'description': description,
            }
        }
        return self._put(url, body)

    def del_security_groups(self, region, id_):
        """
        刪除安全組
        -----
        Parameters:
            region(str): 機房名稱
            id_(str): 安全組ID
        """
        path = '/security-groups/{}'.format(id_)
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._delete(url)

    def security_group_rules(self, region, *args, **kwargs):
        """
        安全組規則列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = '/security-group-rules'
        url = self.get_url(region, 'network', path)
        return self._get(url, kwargs)

    def security_group_rules_by_group_id(self, region, group_id):
        """
        安全組規則列表
        -----
        Parameters:
            region(str): 機房名稱
            group_id(str): 組id
        """
        path = f'/security-group-rules?security_group_id={group_id}'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def security_group_rules_by_id(self, region, id_):
        """
        查詢單一安全組規則
        -----
        Parameters:
            region(str): 機房名稱
            id_(str): 規則ID
        """
        path = '/security-group-rules/{}'.format(id_)
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def add_security_group_rules(
        self,
        region,
        security_group_id,
        remote_group_id,
        remote_ip_prefix,
        port_range_min,
        port_range_max,
        ethertype='IPv4',
        description='',
        protocol='tcp',
        direction='ingress',
        *args,
        **kwargs,
    ):
        """
        增加安全組規則
        -----
        Parameters:
            region(str): 機房名稱
            security_group_id(str): 安全組ID
            remote_group_id(str): 遠端安全組ID
            remote_ip_prefix: 遠端IP段
            port_range_min(int): 開放端口
            port_range_max(int): 開放端口
            ethertype(str): IPv4 or IPv6
            protocol(str): tcp or udp
            direction(str): 方向
        """
        path = '/security-group-rules'
        url = self.get_url(region, 'network', path)
        body = {
            'security_group_rule': {
                'security_group_id': security_group_id,
                'remote_group_id': remote_group_id,
                'port_range_min': port_range_min,
                'port_range_max': port_range_max,
                'description': description,
                'direction': direction,
                'protocol': protocol,
                'ethertype': ethertype,
                'remote_ip_prefix': remote_ip_prefix,
            }
        }
        return self._post(url, body)

    def del_security_group_rules(self, region, id_):
        """
        刪除規則
        -----
        Parameters:
            region(str): 機房名稱
            id_(str): 規則ID
        """
        path = '/security-group-rules/{}'.format(id_)
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._delete(url)

    def ports(self, region, port_id=None):
        """
        查詢 ports 列表
        -----
        Parameters:
            region(str): 機房名稱
        """
        path = f'/ports/{port_id}' if port_id else '/ports'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._get(url)

    def add_port(self, region, network_id, fixed_ips=None, security_groups=None):
        """
        新增 ports
        -----
        Parameters:
            region(str): 機房名稱
            network_id(str): 網路ID
        """
        path = '/ports'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result

        url = result.data
        body = {'port': {'network_id': network_id, 'description': 'Create by SA_cloud_api'}}
        if fixed_ips:
            body['port']['fixed_ips'] = fixed_ips

        if security_groups:
            body['port']['security_groups'] = security_groups

        return self._post(url, body)

    def put_ports(self, region, port_id, **kwargs):
        """
        修改 ports
        -----
        Parameters:
            region(str): 機房名稱
            port_id(str): Port ID

        """
        path = f'/ports/{port_id}'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result

        return self._put(result.data, {'port': kwargs})

    def del_ports(self, region, port_id, **kwargs):
        """
        刪除 ports
        -----
        Parameters:
            region(str): 機房名稱
            port_id(str): Port ID

        """
        path = f'/ports/{port_id}'
        result = self.get_url(region, 'network', path)
        if not result.OK:
            return result
        url = result.data
        return self._delete(url)

    def create_servers(
        self,
        region,
        name,
        ip,
        network_id,
        image_id,
        flavor_id,
        server_group_id,
        security_group=None,
        availability_zone=None,
        key=None,
        port_id=None,
        metadata=None,
        **kwargs,
    ):
        """
        創建服務器
        -----
        Parameters
            region(str): 機房名稱
            name(str): 服務器名稱
            ip(str): ip地址
            network_id(str): 網段ID
            key(str): 密鑰
            image_id(str): 鏡像名稱
            flavor_id(str): 套餐ID
            server_group_id(str): 服務器組ID
            security_group(list): 安全組
            availability_zone(str): 可用區
            port_id(str): Port創建ID
            metadata(dict): 屬性
        """
        path = '/servers'
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            'server': {
                'name': name,
                'imageRef': image_id,
                'flavorRef': flavor_id,
                'max_count': 1,
                'min_count': 1,
            },
            'OS-SCH-HNT:scheduler_hints': {
                'group': server_group_id,
            },
        }
        if security_group:
            security_gourp_list = [{'name': n} for n in security_group]
            body['server']['security_groups'] = security_gourp_list
        if availability_zone:
            body['server']['availability_zone'] = availability_zone

        if key:
            body['server']['key_name'] = key

        if port_id is None:
            body['server']['networks'] = [
                {
                    'fixed_ip': ip,
                    'uuid': network_id,
                }
            ]
        else:
            body['server']['networks'] = [
                {
                    'port': port_id,
                }
            ]

        if metadata and isinstance(metadata, dict):
            body['server']['metadata'] = metadata

        try:
            resp = self.http_client.post(url, json=body, headers=self.header)
            if resp.status_code not in [200, 201, 202, 204]:
                self.result.set(resp.text, False)
                return self.result
            data = json.loads(resp.text)
            self.result.set(data)
        except Exception:
            self.result.set(traceback.format_exc(), False)
            return self.result
        return self.result

    def del_server(self, region, server_id):
        """
        刪除服務器
        -----
        Parameters
            region(str): 機房
            server_id(str): 服務器ID
        """
        path = '/servers/{}'.format(server_id)
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        return self._delete(url)

    def action_server(self, region, server_id, action, body=None):
        """
        操作服務器
        -----
        Parameters
            region(str): 機房
            server_id(str): 服務器ID
            action(str): 動作
        """
        path = '/servers/{}/action'.format(server_id)
        result = self.get_url(region, 'compute', path)
        if not result.OK:
            return result
        url = result.data
        body = {
            action: body,
        }
        return self._post(url, body)

    def get_users(self):
        """獲取使用者"""

        return self._get(self.identity_url + '/users')

    def get_user_group(self, user_id):
        """獲取使用者羣組"""

        return self._get(self.identity_url + f'/users/{user_id}/groups')

    def get_roles(self):
        """獲取規則列表"""

        return self._get(self.identity_url + '/roles')

    def get_compute_quota(self, region, project_id):
        """獲取計算配額

        Return Data: {"quota_set": {"injected_file_content_bytes": 10240, ... }}
        """

        url = self.get_url(region, 'compute', f"/os-quota-sets/{project_id}")
        return self._get(url)

    def put_compute_quota(self, region, project_id, data):
        """更改計算配額"""

        url = self.get_url(region, 'compute', f"/os-quota-sets/{project_id}")
        return self._put(url, data)

    def get_network_quota(self, region, project_id):
        """獲取網路配額

        Return Data: {"quota": {"subnet": 100, ... }}
        """

        url = self.get_url(region, 'network', f"/quotas/{project_id}")
        return self._get(url)

    def put_network_quota(self, region, project_id, data):
        """更改網路配額"""

        url = self.get_url(region, 'network', f"/quotas/{project_id}")
        return self._put(url, data)

    def get_volume_quota(self, region, project_id):
        """獲取卷配額
        只能用admin腳色獲取
        """

        url = self.get_url(
            region, 'volumev3', f"/{self._projects['admin']}/os-quota-sets/{project_id}"
        )
        return self._get(url)
