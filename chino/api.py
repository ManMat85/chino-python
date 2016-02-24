# -*- coding: utf-8 -*-

'''
client for Chino.io API
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2015 by Chino SrlS
:license: Apache 2.0, see LICENSE for more details.
'''
import base64
import hashlib
import json
import os

import requests
from requests.auth import HTTPBasicAuth

from chino.exceptions import MethodNotSupported, CallError, CallFail, ClientError
from chino.objects import Repository, ListResult, User, Group, Schema, Document, Blob, BlobDetail

__author__ = 'Stefano Tranquillini <stefano@chino.io>'

import logging

logger = logging.getLogger(__name__)


class ChinoAPIBase(object):  # PRAGMA: NO COVER
    '''
        Base class, contains the utils methods to call the APIs
    '''
    _url = None
    auth = None

    def __init__(self, auth, url, timeout):
        '''
        Init the class, auth is ref, so it can be changed and changes applies to all the other classes.

        :param auth: 
        :param url: 
        :return:
        '''
        self._url = url
        self.auth = auth
        self.timeout = timeout

    # UTILS
    def apicall(self, method, url, params=None, data=None):
        method = method.upper()
        url = self._url + url
        # logger.debug("calling %s %s p(%s) d(%s)" % (method, url, params, data))
        if method == 'GET':
            res = self._apicall_get(url, params)
        elif method == 'POST':
            res = self._apicall_post(url, data)
        elif method == 'PUT':
            res = self._apicall_put(url, data)
        elif method == 'DELETE':
            res = self._apicall_delete(url, params)
        else:
            raise MethodNotSupported
        self.valid_call(res)
        try:
            # if result has data
            data = res.json()['data']
            return data
        except:
            # emtpy response without errors, return True
            return True

    def _apicall_put(self, url, data):
        if hasattr(data, 'to_dict()'):
            d = data.to_dict()
        else:
            d = data
        r = requests.put(url, auth=self._get_auth(), data=json.dumps(d), timeout=self.timeout)
        return r

    def _apicall_post(self, url, data):
        if hasattr(data, 'to_dict()'):
            d = data.to_dict()
        else:
            d = data
        r = requests.post(url, auth=self._get_auth(), data=json.dumps(d), timeout=self.timeout)
        return r

    def _apicall_get(self, url, params):
        r = requests.get(url, auth=self._get_auth(), params=params, timeout=self.timeout)
        return r

    def _apicall_delete(self, url, params):
        r = requests.delete(url, auth=self._get_auth(), params=params, timeout=self.timeout)
        return r

    def _get_auth(self):
        return self.auth.get_auth()

    @staticmethod
    def valid_call(r):
        # logger.debug("%s Response %s ", r.request.url, r.json())
        if r.status_code == requests.codes.ok:
            return True
        else:
            try:
                status = r.json()['result']
            except:
                raise CallError(code=500, message="Something went wrong with the server")
            if status == 'error':
                raise CallError(code=r.status_code, message=r.json()['message'])
            elif status == 'fail':
                raise CallFail(code=r.status_code, message=r.json()['data'])
            else:
                raise CallError(code=r.status_code, message=r.json())


class ChinoAPIUsers(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIUsers, self).__init__(auth, url, timeout)

    def login(self, username, password, customer_id=None):
        # remove auth and save in temp var (in case of problems)

        auth = self.auth
        # self.auth = None
        url = "auth/login"
        if not customer_id:
            customer_id = self.auth.customer_id
        pars = dict(username=username, password=password, customer_id=customer_id)
        try:
            user = self.apicall('POST', url, data=pars)['user']
            self.auth.access_token = user['access_token']
            self.auth.set_auth_user()
            return user
        except Exception as ex:
            # reset auth if things go wrong
            self.auth = auth
            # propagate exception
            raise ex

    def current(self):
        url = "auth/info"
        return User(**self.apicall('GET', url)['user'])

    def logout(self):
        url = "auth/logout"
        return self.apicall('POST', url)

        # USER

    def list(self, **pars):
        url = "users"
        return ListResult(User, self.apicall('GET', url, params=pars))

    def detail(self, user_id):
        url = "users/%s" % user_id
        return User(**self.apicall('GET', url)['user'])

    def create(self, username, password, attributes=None):
        data = dict(username=username, password=password, attributes=attributes, )
        url = "users"
        return User(**self.apicall('POST', url, data=data)['user'])

    def update(self, user_id, **kwargs):
        url = "users/%s" % user_id
        u_updated = self.apicall('PUT', url, data=kwargs)['user']
        return User(**u_updated)

    def delete(self, user_id, force=False):
        url = "users/%s" % user_id
        if force:
            params = dict(force='true')
        else:
            params = None
        return self.apicall('DELETE', url, params)


class ChinoAPIGroups(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIGroups, self).__init__(auth, url, timeout)

    def list(self, **pars):
        url = "groups"
        return ListResult(Group, self.apicall('GET', url, params=pars))

    def detail(self, group_id):
        url = "groups/%s" % group_id
        return Group(**self.apicall('GET', url)['group'])

    def create(self, groupname, attributes=None):
        data = dict(groupname=groupname, attributes=attributes)
        url = "groups"
        return Group(**self.apicall('POST', url, data=data)['group'])

    def update(self, group_id, **kwargs):
        print kwargs
        url = "groups/%s" % group_id
        return self.apicall('PUT', url, data=kwargs)['group']

    def delete(self, group_id, force=False):
        url = "groups/%s" % group_id
        if force:
            params = dict(force='true')
        else:
            params = None
        return self.apicall('DELETE', url, params)

    def add_user(self, group_id, user_id):
        url = "groups/%s/users/%s" % (group_id, user_id)
        return self.apicall('POST', url)

    def del_user(self, group_id, user_id):
        url = "groups/%s/users/%s" % (group_id, user_id)
        return self.apicall('DELETE', url)


class ChinoAPIPermissions(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIPermissions, self).__init__(auth, url, timeout)

    def user(self, user_id):
        url = "perms/users/%s" % user_id
        return self.apicall('GET', url)

    def create_user(self, schema_id, user_id, own_data, all_data, insert=True):
        data = dict(permissions=dict(own_data=own_data, all_data=all_data, insert=insert))
        url = "perms/schemas/%s/users/%s" % (schema_id, user_id)
        return self.apicall('POST', url, data=data)

    def delete_user(self, schema_id, user_id):
        url = "perms/schemas/%s/users/%s" % (schema_id, user_id)
        return self.apicall('DELETE', url)

    def group(self, group_id):
        url = "perms/groups/%s" % group_id
        return self.apicall('GET', url)

    def schema(self, schema_id):
        url = "perms/schemas/%s" % schema_id
        return self.apicall('GET', url)

    def create_group(self, schema_id, group_id, own_data, all_data, insert=True):
        data = dict(permissions=dict(own_data=own_data, all_data=all_data, insert=insert))
        url = "perms/schemas/%s/groups/%s" % (schema_id, group_id)
        return self.apicall('POST', url, data=data)

    def delete_group(self, schema_id, group_id):
        url = "perms/schemas/%s/groups/%s" % (schema_id, group_id)
        return self.apicall('DELETE', url)


class ChinoAPIRepositories(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIRepositories, self).__init__(auth, url, timeout)

    def list(self, **pars):
        """
        Gets the list of repository

        :param: usual for a list ``offset``, ``limit``
        :return: dict containing ``count``,``total_count``,``limit``,``offset`` and the list of items
        inside a property with its name (e.g., ``documents``)
        """
        url = "repositories"
        return ListResult(Repository, self.apicall('GET', url, params=pars))

    def detail(self, repository_id):
        """
        Gets the details of repository.

        :param repository_id: (id) the id of the repository
        :return: (dict) the repository.
        """
        url = "repositories/%s" % repository_id
        return Repository(**self.apicall('GET', url)['repository'])

    def create(self, description):
        """
        Creates a a repository.

        :param description: (str) the name of the repository
        :return: (dict) the repository.
        """
        data = dict(description=description)
        url = "repositories"
        return Repository(**self.apicall('POST', url, data=data)['repository'])

    def update(self, repository_id, **kwargs):
        """
        Update a a repository.

        :param repository_id: (id) the id of the repository
        :param description: (str) the name of the repository
        :return: (dict) the repository.
        """
        url = "repositories/%s" % repository_id
        return Repository(**self.apicall('PUT', url, data=kwargs)['repository'])

    def delete(self, repository_id, force=False):
        """
        Creates a a repository.

        :param repository_id: (id) the id of the repository
        :return: None
        """
        url = "repositories/%s" % repository_id
        if force:
            params = dict(force='true')
        else:
            params = None
        return self.apicall('DELETE', url, params)


class ChinoAPISchemas(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPISchemas, self).__init__(auth, url, timeout)

    def list(self, repository_id, **pars):
        """
        Gets the list of docuemnts by schema

        :param repository_id: (id) the id of the repository
        :param: usual for a list ``offset``, ``limit``
        :return: dict containing ``count``,``total_count``,``limit``,``offset``,``repositories``
        """
        url = "repositories/%s/schemas" % repository_id
        return ListResult(Schema, self.apicall('GET', url, params=pars))

    def create(self, repository, description, fields):
        """
        Creates a schema in a repository.

        :param repository: (id) the repository in which the schema is created
        :param description: (str) the name of the schema
        :param fields: list(dict) the list of fields
        :return: (dict) the schema.
        """
        data = dict(description=description, structure=dict(fields=fields))
        url = "repositories/%s/schemas" % repository
        return Schema(**self.apicall('POST', url, data=data)['schema'])

    def detail(self, schema_id):
        """
        Details of a schema in a repository.

        :param schema_id: (id) of the schema
        :return: (dict) the schema.
        """
        url = "schemas/%s" % schema_id
        return Schema(**self.apicall('GET', url)['schema'])

    def update(self, schema_id, **kwargs):
        url = "schemas/%s" % schema_id
        return Schema(**self.apicall('PUT', url, data=kwargs)['schema'])

    def delete(self, schema_id, force=False):
        url = "schemas/%s" % schema_id
        if force:
            params = dict(force='true')
        else:
            params = None
        return self.apicall('DELETE', url, params)


class ChinoAPIDocuments(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIDocuments, self).__init__(auth, url, timeout)

    def list(self, schema_id, **pars):
        url = "schemas/%s/documents" % schema_id
        return ListResult(Document, self.apicall('GET', url, params=pars))

    def create(self, schema_id, content):
        data = dict(content=content)
        url = "schemas/%s/documents" % schema_id
        return Document(**self.apicall('POST', url, data=data)['document'])

    def detail(self, document_id):
        url = "documents/%s" % document_id
        return Document(**self.apicall('GET', url)['document'])

    def update(self, document_id, **kwargs):
        # data = dict(content=content)
        url = "documents/%s" % document_id
        return Document(**self.apicall('PUT', url, data=kwargs)['document'])

    def delete(self, document_id, force=False):
        url = "documents/%s" % document_id
        if force:
            params = dict(force='true')
        else:
            params = None
        return self.apicall('DELETE', url, params)


class ChinoAPIBlobs(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPIBlobs, self).__init__(auth, url, timeout)

    def send(self, document_id, blob_field_name, file_path, chunk_size=12 * 1024):
        if not os.path.exists(file_path):
            raise ClientError("File not found")
        # start the blob
        blobdata = self.start(document_id, blob_field_name, os.path.basename(file_path))
        # get the id and intial offset
        upload_id = blobdata['upload_id']
        offset = 0
        # open the file and start reading it
        logger.debug("file size %s", os.path.getsize(file_path))
        rd = open(file_path, "rb")

        sha1 = hashlib.sha1()
        chunk = ""
        byte = rd.read(1)
        chunk += byte
        actual_size = 1
        # read all the file
        while byte != "":
            # if enough byte are read
            if actual_size == chunk_size:
                # send a cuhnk
                blobdata = self.chunk(upload_id, chunk, offset)
                # update offset
                offset = blobdata['offset']
                # update the hash
                sha1.update(chunk)
                chunk = ""
                actual_size = 0
            # read the byte
            byte = rd.read(1)
            actual_size += 1
            chunk += byte
        # if end of the file
        if actual_size != 0:
            self.chunk(upload_id, chunk, offset)
            sha1.update(chunk)
        rd.close()
        # commit and check if everything was fine
        commit = self.commit(upload_id)
        if sha1.hexdigest() != commit['sha1']:
            raise CallFail(500, 'The file was not uploaded correctly')
        return BlobDetail(**commit)

    def start(self, document_id, field, field_name):
        url = 'blobs'
        data = dict(document_id=document_id, field=field, file_name=field_name)
        return self.apicall('POST', url, data=data)['blob']

    def chunk(self, upload_id, data, offset):
        url = 'blobs'
        data = dict(upload_id=upload_id, data=base64.b64encode(data), offset=offset)
        return self.apicall('PUT', url, data=data)['blob']

    def commit(self, upload_id):
        url = 'blobs/commit'
        data = dict(upload_id=upload_id)
        return self.apicall('POST', url, data=data)['blob']

    def detail(self, blob_id):
        # NOTE: this calls directly the function. needed to get the headers
        url = self._url + 'blobs/%s' % blob_id
        # this is different
        res = self._apicall_get(url, None)
        fname = res.headers['Content-Disposition'].split(';')[1].split('=')[1]
        return Blob(filename=fname, content=res.content)

    def delete(self, blob_id):
        url = 'blobs/%s' % blob_id
        return self.apicall('DELETE', url)


class ChinoAPISearches(ChinoAPIBase):
    def __init__(self, auth, url, timeout):
        super(ChinoAPISearches, self).__init__(auth, url, timeout)

    def search(self, schema_id, result_type="FULL_CONTENT", filter_type="and", sort=None, filters=None):
        url = 'search'
        if not sort:
            sort = []
        if not filters:
            filters = []
        data = dict(schema_id=schema_id, result_type=result_type, filter_type=filter_type, sort=sort, filters=filters)
        return self.apicall('POST', url, data=data)['documents']


class ChinoAuth(object):
    customer_id = None
    customer_key = None
    access_token = None
    ACCESS_TOKEN = 'ACCESS_TOKEN'
    __auth = None

    # TODO: write docstring
    def __init__(self, customer_id, customer_key=None, access_token=None):
        '''
        Init the class

        :param customer_id: mandatory
        :param customer_key: optional, if specified the auth is set as chino customer (admin)
        :param access_token: optional, if specified the auth is as user
        :param version: default is `v1`, change if you know what to do
        :param url: the url, this should be changed only for testing
        :return: the class
        '''
        self.customer_id = customer_id
        self.customer_key = customer_key
        self.access_token = access_token
        # if customer_key is set, then set auth as that
        if customer_key:
            self.set_auth_admin()
        # if access_token is set, then use it as customer
        elif access_token:
            self.set_auth_user()

    def set_auth_admin(self):
        self.__auth = HTTPBasicAuth(self.customer_id, self.customer_key)

    def set_auth_user(self):
        self.__auth = HTTPBasicAuth(self.ACCESS_TOKEN, self.access_token)

    def get_auth(self):
        return self.__auth


class ChinoAPIClient(object):
    """
    ChinoAPI the client class
    """

    users = groups = permissions = repositories = schemas = documents = blobs = searches = None

    def __init__(self, customer_id, customer_key=None, customer_token=None, version='v1', url='https://api.chino.io/',
                 timeout=30):
        '''
        Init the class

        :param customer_id: mandatory
        :param customer_key: optional, if specified the auth is set as chino customer (admin)
        :param customer_token: optional, if specified the auth is as user
        :param version: default is `v1`, change if you know what to do
        :param url: the url, this should be changed only for testing
        :return: the class
        '''

        # smarter wayt o add slash?
        final_url = url + version + '/'
        auth = ChinoAuth(customer_id, customer_key, customer_token)
        self.auth = auth
        self.users = ChinoAPIUsers(auth, final_url, timeout)
        self.groups = ChinoAPIGroups(auth, final_url, timeout)
        self.permissions = ChinoAPIPermissions(auth, final_url, timeout)
        self.repositories = ChinoAPIRepositories(auth, final_url, timeout)
        self.schemas = ChinoAPISchemas(auth, final_url, timeout)
        self.documents = ChinoAPIDocuments(auth, final_url, timeout)
        self.blobs = ChinoAPIBlobs(auth, final_url, timeout)
        self.searches = ChinoAPISearches(auth, final_url, timeout)
