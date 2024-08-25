class StringUtil(object):
    """
    字符串校驗util
    """
    @staticmethod
    def is_empty(obj):
        if obj is None:
            return True
        if isinstance(obj, str):
            if len(obj.strip()) == 0:
                return True
        elif isinstance(obj, int):
            if obj is not None:
                return False
        else:
            return False
        return False

    @staticmethod
    def is_equals(str1, str2):
        """
        字符串對比是否相等
        :param str1:
        :param str2:
        :return:
        """
        if StringUtil.is_empty(str1) and StringUtil.is_empty(str2):
            return True
        if StringUtil.is_empty(str1) or StringUtil.is_empty(str2):
            return False
        if type(str1) != type(str2):
            if type(str1) == int:
                str1 = str(str1)
            if type(str2) == int:
                str2 = str(str2)
        if str1 == str2:
            return True
        return False
