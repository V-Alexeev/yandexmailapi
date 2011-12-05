"""Copyright (c) 2011, Vasily Alexeev <mail@v-alexeev.ru>
 All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright notice,
        this list of conditions and the following disclaimer in the documentation
        and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
OF SUCH DAMAGE.



A simple to use and seemingly complete Yandex Mail For Domain API wrapper
    Official manual: http://pdd.yandex.ru/help/section72/

    Partly based on http://narod.ru/disk/get/20174304000/python_lib_api.zip.html

    Scroll down to see command signatures
"""

import urllib
import xml.etree.ElementTree as ElementTree

from datetime import datetime


API_URL = 'https://pddimp.yandex.ru/'


class YandexApiException(BaseException):
    def __init__(self, message, url, params):
        message += ' Request: [url %s] [params %s]' % (url, params)
        super(YandexApiException, self).__init__(message)
        

class YandexMailApi(object):
    def __init__(self, api_token):
        self.token = api_token

    def runCommand(self, command_name, params, response_handler=None):
        if response_handler is None: response_handler = self.simpleResponseHandler
        params.pop('self', None)
        params = dict((k,v) for k,v in params.iteritems() if v)
        params['token'] = self.token
        params = urllib.urlencode(params)
        url = ''.join((API_URL, command_name, '.xml'))
        xml = urllib.urlopen(url, params).read()

        if not xml:
            raise YandexApiException("No valid response received", url, params)

        xml = ElementTree.fromstring(xml)
        error = xml.find('error')
        if error is not None:
            raise YandexApiException(error.get('reason'), url, params)

        result = response_handler(xml)

        if result is None:
            raise YandexApiException("No valid response received", url, params)

        return result


# Response handlers
    @staticmethod
    def simpleResponseHandler(xml): # Simple ok/error response
        if xml.find('ok') is not None:
            return True


    @staticmethod
    def okAttrResponseHandler(xml): # Response with meaningful <ok/> attributes
        ok_tag = xml.find('ok')
        if ok_tag is not None:
            result = {}
            for name, value in ok_tag.items():
                # Let's guess attribute type
                converted_value = None
                try:
                    converted_value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        converted_value = int(value)
                    except ValueError:
                        try:
                            converted_value = value.decode('cp1251')
                        except UnicodeDecodeError:
                            pass
                result[name] = converted_value if converted_value is not None else value

            return result


    @staticmethod
    def checkUserHandler(xml): # check_user is a special case
        tag = xml.find('result')
        if tag.text == "exists":
            return True
        elif tag.text == "nouser":
            return False
        

    @staticmethod
    def responseHandlerFactory(response_template):
        """
            response_template should be a dictionary describing structure of the response.

            Example (for getUsersList command):

            {'emails':
                {'action-status': unicode,
                'email': [{'name': unicode}],
                'found': int,
                'total': int
                },
            'name': unicode,
            'status': unicode,
            'emails-max-count': int
            }

            I.e. specify the expected type of tag's value. If there may be several such tags, put them in a (1-element long) list.

            Note: instead of using template, values could be parsed automatically in a way similar to okAttrResponseHandler.
            But with the templates the process is more explicit and predictable. And templates also serve as documentation.

            (the same goes for command signatures, they are pretty useless except as documentation)
        """
        def responseHandler(xml):
            def parseXml(xml, template):
                result = {}
                for tag_name in template:
                    tags = list(xml.iter(tag_name))
                    if not tags:
                        result[tag_name] = None
                    elif template[tag_name] is int:
                        result[tag_name] = int(tags[0].text)
                    elif template[tag_name] is unicode:
                        result[tag_name] = tags[0].text
                        if result[tag_name] and type(tags[0].text) != unicode:
                            result[tag_name] = result[tag_name].decode('cp1251')
                    elif template[tag_name] is datetime:
                        result[tag_name] = tags[0].text
                        if result[tag_name]: result[tag_name] = datetime.strptime(result[tag_name], '%Y-%m-%d')
                    elif isinstance(template[tag_name], dict):
                        result[tag_name] = parseXml(tags[0], template[tag_name])
                    elif isinstance(template[tag_name], list):
                        result[tag_name] = [parseXml(tag, template[tag_name][0]) for tag in tags]
                return result

            
            return parseXml(xml, response_template)

        return responseHandler


    @classmethod # Had to make it class method to be able to reference responseHandlerFactory
    def authResponseHandlerWrapper(cls, error_return_path):
        def authResponseHandler(xml):
            first_pass = cls.responseHandlerFactory(
                    {
                         'name': unicode,
                         'email':
                        {
                             'name': unicode,
                             'oauth-token': unicode,
                         }
                     })(xml)
            oauth_token = first_pass['email']['oauth-token']
            result = "http://passport.yandex.ru/passport?mode=oauth&access_token=%s&type=trusted-pdd-partner" % (oauth_token,)
            if error_return_path is not None:
                result = ''.join((result, '&error_retpath=', urllib.quote_plus(error_return_path)))
            return result

        return authResponseHandler
    

###################
# Command signatures
###################

# Operations with users
        
    def createUser(self, u_login, u_password):
        return self.runCommand('reg_user_token', locals())

    def checkUserExistence(self, login):
        return self.runCommand('check_user', locals(), response_handler=self.checkUserHandler)

    def deleteUser(self, login):
        return self.runCommand('delete_user', locals())

    def editUserDetails(self, login, new_password = None, iname = None, fname = None, sex = None):
        """
        Sex: 1 - male; 2 - female
        iname - first name
        fname - last name

        """
        return self.runCommand('edit_user', locals())

    def setDefaultDomainUser(self, domain, login):
        return self.runCommand('api/reg_default_user', locals(),
            response_handler=self.responseHandlerFactory(
                    {
                         'name': unicode,
                         'default-email': unicode,
                    }))

    def getUnreadMessagesCount(self, login):
        return self.runCommand('get_mail_info', locals(), response_handler=self.okAttrResponseHandler)

    def getUserInfo(self, login):
        return self.runCommand('get_user_info', locals(),
            response_handler=self.responseHandlerFactory(
                    {
                         'name': unicode,
                         'user': {
                             'login': unicode,
                             'birth_date': datetime,
                             'fname': unicode,
                             'iname': unicode,
                             'hinta': unicode,
                             'hintq': unicode,
                             'mail_format': unicode,
                             'charset': unicode,
                             'nickname': unicode,
                             'sex': int,
                             'enabled': int,
                             'signed_eula': int,
                         },
                    }))

    def getUsersList(self, page = 1, perpage = 100):
        return self.runCommand('get_domain_users', locals(),
            response_handler=self.responseHandlerFactory(
                    {'emails':
                        {'action-status': unicode,
                        'email': [{'name': unicode}],
                        'found': int,
                        'total': int,
                        },
                    'name': unicode,
                    'status': unicode,
                    'emails-max-count': unicode,
                    }))

    def createDomainUser(self, domain, login, passwd=None):
        return self.runCommand('api/reg_user', locals(),
            response_handler=self.responseHandlerFactory(
                    {
                         'name': unicode,
                         'email': {'name': unicode},
                    }))

    def delDomainUser(self, domain, login):
        return self.runCommand('api/del_user', locals(),
            response_handler=self.responseHandlerFactory(
                    {
                         'name': unicode,
                         'email': {'name': unicode},
                    }))

# Import from old mailboxes

    def setImportSettings(self, method, ext_serv, ext_port = None, isssl = "no", callback = None):
        return self.runCommand('set_domain', locals())

    def startImport(self, login, ext_login, password):
        return self.runCommand('start_import', locals())

    def getImportState(self, login):
        return self.runCommand('check_import', locals(), response_handler=self.okAttrResponseHandler)

    def registerAndStartImport(self, login, inn_password, ext_login, ext_password):
        return self.runCommand('reg_and_imp', locals())

    def stopImport(self, login):
        return self.runCommand('stop_import', locals())

# Authentication

    def getAuthUrl(self, domain, login, error_return_path=None):
        return self.runCommand('api/user_oauth_token', locals(),
                               response_handler=self.authResponseHandlerWrapper(error_return_path))

    def setUrlCallback(self, domain_name, callback, error_return_path=None):
        """
            Callback should be URL-encoded
        """
        return self.runCommand('api/set_mail_callback', locals(),
                               response_handler=self.authResponseHandlerWrapper(error_return_path))

# Filters

    def getFilters(self, login):
        return self.runCommand('get_forward_list', locals(),
            response_handler=self.responseHandlerFactory({'filters': [{'filter': unicode}]}))

    def delFilter(self, login, filter_id):
        return self.runCommand('delete_forward', locals())

# Operations with domains

    def addDomain(self, domain):
        return self.runCommand('api/reg_domain', locals(),
            response_handler=self.responseHandlerFactory(
            {
                        'name': unicode,
                        'secret_name': unicode,
                        'secret_value': unicode,
            }))

    def delDomain(self, domain):
        return self.runCommand('api/del_domain', locals(),
            response_handler=self.responseHandlerFactory(
            {
                         'name': unicode,
            }))

    def addLogo(self, domain):
        return self.runCommand('api/add_logo', locals(),
            response_handler=self.responseHandlerFactory(
                {'domain': {'name': unicode,},
                 'logo': {'url': unicode,}
                }
            ))

    def delLogo(self, domain):
        return self.runCommand('api/del_logo', locals(),
            response_handler=self.responseHandlerFactory(
            {'name': unicode,}))

# Operations with administrators

    def addAdmin(self, domain, login):
        return self.runCommand('api/multiadmin/add_admin', locals(),
            response_handler=self.responseHandlerFactory(
            {
                'name': unicode,
                'new-admin': unicode,
            }))

    def delAdmin(self, domain, login):
        return self.runCommand('api/multiadmin/del_admin', locals(),
            response_handler=self.responseHandlerFactory(
            {
                'name': unicode,
                'new-admin': unicode,
            }))

    def listAdmins(self, domain):
        return self.runCommand('api/multiadmin/get_admins', locals(),
            response_handler=self.responseHandlerFactory(
            {
                'name': unicode,
                'other-admins': [{'login': unicode,}],
            }))

# Operations with mailing lists

    def createGeneralMaillist(self, domain, ml_name):
        return self.runCommand('api/create_general_maillist', locals(),
            response_handler=self.responseHandlerFactory(
            {
                'name': unicode,
            }))

    def deleteGeneralMaillist(self, domain):
        return self.runCommand('api/delete_general_maillist', locals(),
            response_handler=self.responseHandlerFactory(
            {
                'name': unicode,
            }))