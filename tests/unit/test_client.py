#!/usr/bin/env
# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
from tests import unittest
import mock

from botocore import model
from botocore import client
from botocore import hooks
from botocore.client import ParamValidationError
from botocore import exceptions


class TestAutoGeneratedClient(unittest.TestCase):
    def setUp(self):
        self.service_description = {
            'metadata': {
                'apiVersion': '2014-01-01',
                'endpointPrefix': 'myservice',
                'signatureVersion': 'v4',
                'protocol': 'query'
            },
            'operations': {
                'TestOperation': {
                    'name': 'TestOperation',
                    'http': {
                        'method': 'POST',
                        'requestUri': '/',
                    },
                    'input': {'shape': 'TestOperationRequest'},
                }
            },
            'shapes': {
                'TestOperationRequest': {
                    'type': 'structure',
                    'required': ['Foo'],
                    'members': {
                        'Foo': {'shape': 'StringType'},
                        'Bar': {'shape': 'StringType'},
                    }
                },
                'StringType': {'type': 'string'}
            }
        }
        self.loader = mock.Mock()
        self.loader.load_service_model.return_value = self.service_description

    def create_client_creator(self, endpoint_creator=None, event_emitter=None):
        if endpoint_creator is None:
            endpoint_creator = mock.Mock()
        if event_emitter is None:
            event_emitter = hooks.HierarchicalEmitter()
        creator = client.ClientCreator(
            self.loader, endpoint_creator, event_emitter)
        return creator

    def test_client_generated_from_model(self):
        creator = self.create_client_creator()
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertTrue(hasattr(service_client, 'test_operation'))

    def test_client_makes_call(self):
        endpoint_creator = mock.Mock()
        endpoint = mock.Mock()
        endpoint_creator.create_endpoint.return_value = endpoint
        endpoint.make_request.return_value = (mock.Mock(status_code=200), {})
        creator = self.create_client_creator(endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        response = service_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(response, {})

    def test_client_makes_call_with_error(self):
        endpoint_creator = mock.Mock()
        endpoint = mock.Mock()
        endpoint_creator.create_endpoint.return_value = endpoint
        error_response = {
            'Error': {'Code': 'code', 'Message': 'error occurred'}
        }
        endpoint.make_request.return_value = (mock.Mock(status_code=400),
                                              error_response)
        creator = self.create_client_creator(endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(client.ClientError):
            service_client.test_operation(Foo='one', Bar='two')

    def test_client_validates_params(self):
        endpoint_creator = mock.Mock()
        creator = self.create_client_creator(endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(ParamValidationError):
            # Missing required 'Foo' param.
            service_client.test_operation(Bar='two')

    def test_client_with_custom_params(self):
        endpoint_creator = mock.Mock()
        creator = self.create_client_creator(endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2',
                                               is_secure=False, verify=False)
        endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=False,
            endpoint_url=None, verify=False, credentials=None)

    def test_client_with_endpoint_url(self):
        endpoint_creator = mock.Mock()
        creator = self.create_client_creator(endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2',
                                               endpoint_url='http://custom.foo')
        endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=True,
            endpoint_url='http://custom.foo', verify=None, credentials=None)

    def test_operation_cannot_paginate(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                # Note that there's no pagination config for
                # 'TestOperation', indicating that TestOperation
                # is not pageable.
                'SomeOtherOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    def test_operation_can_paginate(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertTrue(service_client.can_paginate('test_operation'))
        # Also, the config is cached, but we want to make sure we get
        # the same answer when we ask again.
        self.assertTrue(service_client.can_paginate('test_operation'))

    def test_service_has_no_pagination_configs(self):
        # This is the case where there is an actual *.paginator.json, file,
        # but the specific operation itself is not actually pageable.
        endpoint_creator = mock.Mock()
        # If the loader cannot load pagination configs, it communicates
        # this by raising a DataNotFoundError.
        self.loader.load_data.side_effect = exceptions.DataNotFoundError(
            data_path='/foo')
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    def test_waiter_config_uses_service_name_not_endpoint_prefix(self):
        endpoint_creator = mock.Mock()
        waiter_config = {
            'version': 2,
            'waiters': {}
        }
        self.loader.load_data.return_value = waiter_config
        creator = self.create_client_creator(endpoint_creator)
        # We're going to verify that the loader loads a service called
        # 'other-service-name', and even though the endpointPrefix is
        # 'myservice', we use 'other-service-name' for waiters/paginators, etc.
        service_client = creator.create_client('other-service-name',
                                               'us-west-2')
        self.assertEqual(service_client.waiter_names, [])
        # Note we're using other-service-name, not
        # 'myservice', which is the endpointPrefix.
        self.loader.load_data.assert_called_with(
            'aws/other-service-name/2014-01-01.waiters')

    def test_service_has_waiter_configs(self):
        endpoint_creator = mock.Mock()
        waiter_config = {
            'version': 2,
            'waiters': {
                "Waiter1": {
                    'operation': 'TestOperation',
                    'delay': 5,
                    'maxAttempts': 20,
                    'acceptors': [],
                },
                "Waiter2": {
                    'operation': 'TestOperation',
                    'delay': 5,
                    'maxAttempts': 20,
                    'acceptors': [],
                },
            }
        }
        self.loader.load_data.return_value = waiter_config
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertEqual(sorted(service_client.waiter_names),
                         sorted(['waiter_1', 'waiter_2']))
        self.assertTrue(hasattr(service_client.get_waiter('waiter_1'), 'wait'))

    def test_service_has_no_waiter_configs(self):
        endpoint_creator = mock.Mock()
        self.loader.load_data.side_effect = exceptions.DataNotFoundError(
            data_path='/foo')
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertEqual(service_client.waiter_names, [])
        with self.assertRaises(ValueError):
            service_client.get_waiter("unknown_waiter")

    def test_try_to_paginate_non_paginated(self):
        endpoint_creator = mock.Mock()
        self.loader.load_data.side_effect = exceptions.DataNotFoundError(
            data_path='/foo')
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(exceptions.OperationNotPageableError):
            service_client.get_paginator('test_operation')

    def test_successful_pagination_object_created(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        paginator = service_client.get_paginator('test_operation')
        # The pagination logic itself is tested elsewhere (test_paginate.py),
        # but we can at least make sure it looks like a paginator.
        self.assertTrue(hasattr(paginator, 'paginate'))

    def test_can_set_credentials_in_client_init(self):
        endpoint_creator = mock.Mock()
        creator = self.create_client_creator(endpoint_creator)
        service_client = creator.create_client(
            'myservice', 'us-west-2', aws_access_key_id='access_key',
            aws_secret_access_key='secret_key',
            aws_session_token='session_token')

        # Verify that we create an endpoint with a credentials object
        # matching our creds arguments.
        args = endpoint_creator.create_endpoint.call_args
        creds_used_for_client = args[1]['credentials']
        self.assertEqual(creds_used_for_client.access_key, 'access_key')
        self.assertEqual(creds_used_for_client.secret_key, 'secret_key')
        self.assertEqual(creds_used_for_client.token, 'session_token')

    def test_event_emitted_when_invoked(self):
        event_emitter = hooks.HierarchicalEmitter()
        endpoint_creator = mock.Mock()
        endpoint = mock.Mock()
        endpoint_creator.create_endpoint.return_value = endpoint
        endpoint.make_request.return_value = (mock.Mock(status_code=200), {})
        creator = self.create_client_creator(endpoint_creator, event_emitter)

        calls = []
        handler = lambda **kwargs: calls.append(kwargs)
        event_emitter.register('before-call', handler)

        service_client = creator.create_client('myservice', 'us-west-2')
        service_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(len(calls), 1)
