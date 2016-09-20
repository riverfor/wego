# -*- coding: utf-8 -*-
from exceptions import WeChatApiError, WeChatUserError
from urllib import quote
import requests
import json
import hashlib
import re


class WeChatApi(object):
    """
    WeChat Api just do one thing: give params to wechat and get the data what wechat return.
    """

    def __init__(self, settings):

        self.settings = settings
        self.global_access_token = {}

    def get_code_url(self, redirect_url, state='STATE'):
        """
        Get the url which 302 jump back and bring a code.

        :param redirect_url: Jump back url
        :param state: Jump back state
        :return: url
        """

        if redirect_url:
            redirect_url = quote(self.settings.REGISTER_URL + redirect_url[1:])
        else:
            redirect_url = self.settings.REDIRECT_URL

        url = ('https://open.weixin.qq.com/connect/oauth2/authorize?' +
               'appid=%s&redirect_uri=%s' +
               '&response_type=code' +
               '&scope=snsapi_userinfo' +
               '&state=%s#wechat_redirect') % (self.settings.APP_ID, redirect_url, state)

        return url

    def get_access_token(self, code):
        """
        Use code for get access token, refresh token, openid etc.

        :param code: A code see function get_code_url.
        :return: Raw data that wechat returns.
        """

        data = requests.get('https://api.weixin.qq.com/sns/oauth2/access_token', params={
            'appid': self.settings.APP_ID,
            'secret': self.settings.APP_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }).json()

        return data

    def refresh_access_token(self, refresh_token):
        """
        Refresh user access token by refresh token.

        :param refresh_token: function get_access_token returns.
        :return: Raw data that wechat returns.
        """

        data = requests.get('https://api.weixin.qq.com/sns/oauth2/refresh_token', params={
            'appid': self.settings.APP_ID,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }).json()

        if 'errcode' in data.keys():
            return 'error'

        return data

    def get_userinfo(self, openid):
        """
        Get user info with global access token (content subscribe, language, remark and groupid).

        :param openid: User openid.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'access_token': access_token,
            'openid': openid,
            'lang': 'zh_CN'
        }
        data = requests.get('https://api.weixin.qq.com/cgi-bin/user/info', params=data).json()

        if 'errcode' in data.keys():
            raise WeChatApiError('errcode: {}, msg: {}'.format(data['errcode'], data['errmsg']))

        return data

    def set_user_remark(self, openid, remark):
        """
        Set user remark.

        :param openid: User openid.
        :param remark: The remark you want to set.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'openid': openid,
            'remark': remark
        }
        url = 'https://api.weixin.qq.com/cgi-bin/user/info/updateremark?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        if 'errcode' in data.keys() and data['errcode'] != 0:
            raise WeChatApiError('errcode: {}, msg: {}'.format(data['errcode'], data['errmsg']))

    def get_userinfo_by_token(self, openid, access_token):
        """
        Get user info with user access token (without subscribe, language, remark and groupid).

        :param openid: User openid.
        :param access_token: function get_access_token returns.
        :return: Raw data that wechat returns.
        """

        data = requests.get('https://api.weixin.qq.com/sns/userinfo', params={
            'access_token': access_token,
            'openid': openid,
            'lang': 'zh_CN'
        })

        data.encoding = 'utf-8'
        return data.json()

    def get_global_access_token(self):
        """
        Get global access token.

        :return: Raw data that wechat returns.
        """

        data = requests.get("https://api.weixin.qq.com/cgi-bin/token", params={
            'grant_type': 'client_credential',
            'appid': self.settings.APP_ID,
            'secret': self.settings.APP_SECRET
        }).json()

        return data

    @staticmethod
    def _make_xml(k, v=None):
        """
        Recursive generate XML
        """

        if not v:
            v = k
            k = 'xml'
        if type(v) is dict:
            v = ''.join([WeChatApi._make_xml(key, val) for key, val in v.iteritems()])
        if type(v) is list:
            l = len(k)+2
            v = ''.join([WeChatApi._make_xml(k, val) for val in v])[l:(l+1)*-1]
        return '<%s>%s</%s>' % (k, v, k)

    def _analysis_xml(self, xml):
        """
        Convert the XML to dict
        """

        return {k: v for v,k in re.findall('\<.*?\>\<\!\[CDATA\[(.*?)\]\]\>\<\/(.*?)\>', xml)}

    def get_unifiedorder(self, data):

        xml = self._make_xml(data).encode('utf-8')
        data = requests.post('https://api.mch.weixin.qq.com/pay/unifiedorder', data=xml).content

        return self._analysis_xml(data)

    def get_all_groups(self):
        """
        Get all user groups.

        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/groups/get?access_token=%s" % access_token
        req = requests.get(url)

        return req.json()

    def change_group_name(self, groupid, name):
        """
        Change group name.

        :param groupid: Group ID.
        :param name: New name.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'group': {
                'id': groupid,
                'name': name
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/groups/update?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def change_user_group(self, openid, groupid):
        """
        Move user to a new group.

        :param openid: User openid.
        :param groupid: Group ID.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'openid': openid,
            'to_groupid': groupid
        }
        url = 'https://api.weixin.qq.com/cgi-bin/groups/members/update?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def del_group(self, groupid):
        """
        Delete a group.

        :param groupid: Group id.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'group': {
                'id': groupid
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/groups/delete?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def create_menu(self, data):
        """
        Create a menu.

        :param data: Menu data.
        :return: Raw data that wechat returns.
        """
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/menu/create?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf8')).json()

        return data
    

    def create_conditional_menu(self, data):
        """
        Create a conditional menu.

        :param data: Menu data.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/menu/addconditional?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf8')).json()

        return data

    def get_menus(self):
        """
        Get all menus.

        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/menu/get?access_token=%s" % access_token
        data = requests.get(url).json()

        return data

    def del_all_menus(self):
        """
        Delete all menus, contain conditional menu.

        ::return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/menu/delete?access_token=%s" % access_token
        data = requests.get(url).json()
        print data

        return data

    def del_conditional_menu(self, menu_id):
        """
        Delete conditional menus, contain conditional menu.

        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'menuid': menu_id
        }
        url = 'https://api.weixin.qq.com/cgi-bin/menu/delconditional?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_materials(self, material_type, offset, count):
        #TODO

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            "type": material_type,
            "offset": offset,
            "count": count
        }

        url = 'https://api.weixin.qq.com/cgi-bin/material/batchget_material?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def create_scene_qrcode(self, scene_id, expire):
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'expire_seconds': expire, 
            'action_name': 'QR_SCENE', 
            'action_info': {
                'scene': {
                    'scene_id': scene_id
                }
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def create_limit_scene_qrcode(self, scene_id):
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'action_name': 'QR_LIMIT_SCENE', 
            'action_info': {
                'scene': {
                    'scene_id': scene_id
                }
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def create_limit_str_scene_qrcode(self, scene_str):
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'action_name': 'QR_LIMIT_SCENE', 
            'action_info': {
                'scene': {
                    'scene_str': scene_str
                }
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def create_short_url(self, url):

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'action': 'long2short',
            'long_url': url
        }
        url = 'https://api.weixin.qq.com/cgi-bin/shorturl?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_wechat_servers_list(self):
        """
        Get wechat servers list
            
        :param data:
        :return: Raw data that wechat returns.
        """
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self) 
        url = "https://api.weixin.qq.com/cgi-bin/getcallbackip?access_token=%s" % access_token
        data = requests.post(url).json()

        return data
    
    def check_personalized_menu_match(self,user_id):
        """
        Check whether personalized menu match is correct.
    
        :param data:user_id
        :return:Raw data that wechat returns.
        """
        
        data = {
            "user_id": user_id
        }
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/cgi-bin/menu/trymatch?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()
        
        return data

    def get_variation_number_of_user(self, begin_date, end_date):
        """
        Get variation in number od user
        
        :param data:begin_date, end_date
        :return:Raw data that wechat returns.
        """

        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getusersummary?access_token=%s"  % access_token

        data = requests.post(url, data=json.dumps(data)).json()
    
        return data
    
        print data

    def get_user_cumulate(self, begin_date, end_date):
        """
        GET accumulation of user

        :param date:begin_date, end_date
        :return:Raw data that wechat returns.
        """

        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getusercumulate?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_article_summary(self, begin_date, end_date):
        """
        Get article summary

        :param data:begin_date, end_date
        :return :Raw data that wechat returns.
        """

        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getarticlesummary?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_article_total(self, begin_date, end_date):
        """
        Get article total

        :param data:begin_date, end_date
        :return :Raw data that wechat returns.
        """
        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getarticletotal?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_user_read(self, begin_date, end_date):
        """
        Get user read

        :param data:begin_date, end_date
        :return :Raw data that wechat returns.
        """
        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getuserread?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()
    
        return data

    def get_user_read_hour(self, begin_date, end_date):
        """
        Get user read hour
        
        param data:begin_date, end_date
        return :Raw data that wechat return.
        """
        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getuserreadhour?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()
        
        return data

    def get_user_share(self, begin_date, end_date):
        """
        Get user share

        param data:begin_data,end_date
        return :Raw data that wechat return.
        """
        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }
        
        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getusershare?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

    def get_user_share_hour(self, begin_date, end_date):
        """
        Get user share
        
        param data:begin_date, end_date
        retur :Raw data that wechat return.
        """
        data = {
            "begin_date": begin_date,
            "end_date": end_date
        }

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        url = "https://api.weixin.qq.com/datacube/getusersharehour?access_token=%s" % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data

#333


# TODO 更方便定制
def get_global_access_token(self):
    """
    获取全局 access token
    """
    def create_group(self, name):
        """
        Create a user group.

        :param name: Group name.
        :return: Raw data that wechat returns.
        """

        access_token = self.settings.GET_GLOBAL_ACCESS_TOKEN(self)
        data = {
            'group': {
                'name': name
            }
        }
        url = 'https://api.weixin.qq.com/cgi-bin/groups/create?access_token=%s' % access_token
        data = requests.post(url, data=json.dumps(data)).json()

        return data
