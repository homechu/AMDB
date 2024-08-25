import os
import subprocess
import re

from main.settings import logger, TERRAFORM_CONF_DIR, TERRAFORM_FILES_DIR


class Base:
    status = False
    dhcp = True

    @property
    def hostname(self):
        hostname = self.vars.get('hostname')
        if hostname:
            return hostname
        else:
            raise Exception("no hostname")

    @property
    def path(self):
        if self.dhcp:
            # logger.info('DHCP 自動發配IP')
            conf = os.path.join(TERRAFORM_CONF_DIR, 'dhcp')
        else:
            # logger.info('靜態IP')
            conf = os.path.join(TERRAFORM_CONF_DIR, 'customip')

        data = {
            'conf': conf,
            'files': os.path.join(TERRAFORM_FILES_DIR, 'files'),
            'host': os.path.join(TERRAFORM_FILES_DIR, 'files', self.hostname)
        }
        return data

    def create_host_dir(self):
        if os.path.exists(self.path['host']):
            # print("更新host目錄")
            pass
        else:
            # print("新建host目錄")
            os.makedirs(self.path['host'])


class Terraform(Base):

    def __init__(self, **kwargs):
        """
        :param kwargs:
            hostname='vm-test87',ipaddress='192.168.10.87'
        """

        self.vars = kwargs
        logger.info("%s\t%s\t%s" % (self.hostname, self.__class__.__name__, kwargs))
        logger.info(self.vars)
        self.run()

    def run(self):
        pass

    def complete(self, ret):
        if 'complete' in ret:
            logger.info('%s complete ok' % self.hostname)
        else:
            logger.info('%s complete error' % self.hostname)
            logger.error(ret)
            raise Exception(f"complete 錯誤 {self.hostname} {ret}")

    def valid(self, ret):
        try:
            string = re.findall('Resources:.(.*)\.', ret)[0]
            num = re.findall('(\d+).%s' % self.valid_text, string)[0]
            if int(num) != 0:
                logger.info('%s valid ok' % self.hostname)
                return True
            else:
                logger.error('%s valid error' % self.hostname)
                return False
        except Exception as e:
            raise Exception(f"Terraform valid 錯誤, {ret}")

    def _init(self):
        os.chdir(self.path['host'])
        ret = subprocess.getoutput(f'terraform init -plugin-dir={os.environ["HOME"]}/.terraform.d/plugin-cache')
        if "Terraform has been successfully initialized!" in ret:
            logger.info('%s terraform init' % self.hostname)
        else:
            raise Exception(f'{self.hostname} terraform init ERROR!\nret')

    def _plan(self):
        ret = subprocess.getoutput('terraform plan -no-color')
        logger.info(f'terraform plan {ret}')

        try:
            plan_string = re.findall('Plan:\s(.*)\.', ret)[0]
            num = re.findall('(\d+).to %s' % self.valid_text, plan_string)[0]
        except Exception as e:
            logger.error(f'Terraform檢查錯誤 {e}', exc_info=True)
            raise Exception(f'Terraform檢查錯誤 {ret}')

        if int(num) != 0:
            logger.info('%s plan ok' % self.hostname)
        else:
            logger.error('%s plan error' % self.hostname)
            raise Exception(f'Terraform檢查錯誤 {ret}')

    def _main(self):
        ret = subprocess.getoutput(self.command)
        self.complete(ret)
        self.valid(ret)
        self.status = True
