from libs.base.exceptions import ValidationMessage


class OpenstackAPIException(ValidationMessage):
    message = 'Openstack 接口錯誤'

    def __init__(self, detail=None):
        self.detail = {'detail': detail}


class OpenstackAPILoginException(OpenstackAPIException):
    message = 'Openstack登入失敗'
