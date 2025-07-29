"""
Copyright 2025 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
import boto3
import json
import logging
import os
from botocore.config import Config


# Set the logger
def set_log_config(logger_obj):
    log_level = os.environ['LOG_LEVEL']
    if log_level.upper() == 'NOTSET':
        logger_obj.setLevel(logging.NOTSET)
    elif log_level.upper() == 'DEBUG':
        logger_obj.setLevel(logging.DEBUG)
    elif log_level.upper() == 'INFO':
        logger_obj.setLevel(logging.INFO)
    elif log_level.upper() == 'WARNING':
        logger_obj.setLevel(logging.WARNING)
    elif log_level.upper() == 'ERROR':
        logger_obj.setLevel(logging.ERROR)
    elif log_level.upper() == 'CRITICAL':
        logger_obj.setLevel(logging.CRITICAL)
    else:
        logger_obj.setLevel(logging.NOTSET)


# Initialize the logger
logger = logging.getLogger()
set_log_config(logger)


# Set the flag to log the LLM prompt and response
LOG_LLM_PROCESSING_INFO = False
if (os.environ['LOG_LLM_PROCESSING_INFO']).upper() == 'TRUE':
    LOG_LLM_PROCESSING_INFO = True


# Substring between strings
def substring_between(source_string, start_string, end_string):
    # Find the index of the start substring
    idx1 = source_string.find(start_string)
    # Find the index of the end substring, starting after the start substring
    idx2 = source_string.find(end_string, idx1 + len(start_string))
    # Check if both delimiters are found and extract the substring between them
    if idx1 != -1 and idx2 != -1:
        return source_string[idx1 + len(start_string):idx2]
    else:
        return ''


# Substring after string
def substring_after(source_string, delimiter):
    string_parts = source_string.split(delimiter, 1)
    if len(string_parts) > 1:
        string_after_substring = string_parts[1]
    else:
        string_after_substring = source_string
    return string_after_substring


# Get the read the content of the specified file
def read_file(file_full_path, file_read_type):
    with open(file_full_path, file_read_type) as file:
        file_content = file.read()
    return file_content


# Get the config for all boto3 clients to be used by this Lambda function
def get_boto_config():
    return Config(
        connect_timeout = (60 * 3),
        read_timeout = (60 * 3),
        retries = {
            'max_attempts': 10,
            'mode': 'standard'
        }
    )


# Check if the instance for the specified id exists
def does_instance_exist_for_id(ec2_client, instance_id):
    # Search for the specified instance
    try:
        ec2_client.describe_instances(
            InstanceIds=[
                instance_id,
            ],
        )
    except Exception as exception:
        return False
    return True


# Check if the volume for the specified id exists
def does_volume_exist_for_id(ec2_client, volume_id):
    # Search for the specified volume
    try:
        ec2_client.describe_volumes(
            VolumeIds=[
                volume_id,
            ],
        )
    except Exception as exception:
        return False
    return True


# Get all the instance ids in the current region in the current account
def get_all_instance_ids(ec2_client):
    instance_ids = []
    describe_instances_response = ec2_client.describe_instances()
    reservations = describe_instances_response['Reservations']
    for reservation in reservations:
        instances = reservation['Instances']
        for instance in instances:
            instance_ids.append(instance['InstanceId'])
    return instance_ids


# Get the instance ids for the specified tags
def get_instance_ids_for_tags(ec2_client, tag_key, tag_values):
    instance_ids = []
    for tag_value in tag_values:
        describe_instances_response = ec2_client.describe_instances(
            Filters=[
                {
                    'Name': 'tag:{}'.format(tag_key),
                    'Values': [
                        tag_value.strip(),
                    ]
                },
            ]
        )
        reservations = describe_instances_response['Reservations']
        for reservation in reservations:
            instances = reservation['Instances']
            for instance in instances:
                instance_ids.append(instance['InstanceId'])
    return instance_ids


# Get the instance ids for the specified names
def get_instance_ids_for_names(ec2_client, instance_names):
    return get_instance_ids_for_tags(ec2_client, 'Name', instance_names)


# Get the snapshots associated with the specified instance ids
def get_snapshots_for_instance_ids(ec2_client, instance_ids):
    snapshots = []
    # Loop through the instance ids
    for instance_id in instance_ids:
        # Get the volumes for the instance id
        describe_volumes_response = ec2_client.describe_volumes(
            Filters=[
                {
                    'Name': 'attachment.instance-id',
                    'Values': [
                        instance_id.strip()
                    ]
                }
            ]
        )
        volume_ids = [volume['VolumeId'] for volume in describe_volumes_response['Volumes']]
        # Loop through the volume ids
        for volume_id in volume_ids:
            # Get the snapshots for the volume id
            describe_snapshots_response = ec2_client.describe_snapshots(
                Filters=[
                    {
                        'Name': 'volume-id',
                        'Values': [volume_id]
                    }
                ],
                OwnerIds=['self']  # Filter for snapshots owned by your account
            )
            # Gather the snapshots info
            snapshots.extend(describe_snapshots_response['Snapshots'])
    return snapshots


# Process the prompt and the response by invoking the specified LLM
def process_prompt(aws_account_id, aws_region, boto3_api_name, user_input, generated_boto3_json_str):
    # Instantiate the Amazon Bedrock runtime boto3 client for the specific region
    bedrock_rt_client = boto3.client('bedrock-runtime', region_name=aws_region, config=get_boto_config())
    # Read the prompt templates and perform variable substitution
    prompt_templates_dir = '.'
    system_prompts = [
        {
            "text": read_file(os.path.join(prompt_templates_dir, os.environ['SYSTEM_PROMPT_FILE_NAME']), 'r')
        }
    ]
    user_prompt_content = read_file(os.path.join(prompt_templates_dir, os.environ['USER_PROMPT_FILE_NAME']), 'r')
    user_prompt_content = user_prompt_content.replace('{aws_account_id}', aws_account_id)
    user_prompt_content = user_prompt_content.replace('{aws_region}', aws_region)
    user_prompt_content = user_prompt_content.replace('{boto3_api_name}', boto3_api_name)
    user_prompt_content = user_prompt_content.replace('{user_input}', user_input)
    user_prompt_content = user_prompt_content.replace('{generated_boto3_json}', generated_boto3_json_str)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": user_prompt_content
                }
            ]
        }
    ]
    # Invoke the LLM, prepare and return the response
    llm_response = invoke_llm(bedrock_rt_client, system_prompts, messages)
    change_log = substring_between(llm_response, '<CHANGELOG>', '</CHANGELOG>')
    logging.info('LLM validation and update complete. Change log :: {}'.format(change_log))
    updated_generated_json = substring_between(llm_response, '<VALIDATED_BOTO3_JSON>', '</VALIDATED_BOTO3_JSON>')
    return updated_generated_json


# Process the prompt for the boto3 API retry and the response by invoking the specified LLM
def process_prompt_for_boto3_api_retry(aws_account_id, aws_region, boto3_api_name, boto3_json_str, boto3_error):
    # Instantiate the Amazon Bedrock runtime boto3 client for the specific region
    bedrock_rt_client = boto3.client('bedrock-runtime', region_name=aws_region, config=get_boto_config())
    # Read the prompt templates and perform variable substitution
    prompt_templates_dir = '.'
    system_prompts = [
        {
            "text": read_file(os.path.join(prompt_templates_dir, os.environ['SYSTEM_PROMPT_FOR_BOTO3_RETRY_FILE_NAME']), 'r')
        }
    ]
    user_prompt_content = read_file(os.path.join(prompt_templates_dir, os.environ['USER_PROMPT_FOR_BOTO3_RETRY_FILE_NAME']), 'r')
    user_prompt_content = user_prompt_content.replace('{aws_account_id}', aws_account_id)
    user_prompt_content = user_prompt_content.replace('{aws_region}', aws_region)
    user_prompt_content = user_prompt_content.replace('{boto3_api_name}', boto3_api_name)
    user_prompt_content = user_prompt_content.replace('{boto3_json}', boto3_json_str)
    user_prompt_content = user_prompt_content.replace('{boto3_error}', boto3_error)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": user_prompt_content
                }
            ]
        }
    ]
    # Invoke the LLM, prepare and return the response
    llm_response = invoke_llm(bedrock_rt_client, system_prompts, messages)
    fixed_boto3_json = substring_between(llm_response, '<FIXED_BOTO3_JSON>', '</FIXED_BOTO3_JSON>')
    logging.info('LLM fix to boto3 JSON completed based on the specified boto3 error.')
    return fixed_boto3_json


# Invoke the specified LLM through Amazon Bedrock's Converse API
def invoke_llm(bedrock_rt_client, system_prompts, messages):
    # Set the inference parameters
    inference_config = {
        "temperature": 0
    }
    additional_model_fields = None
    # Invoke the LLM
    logging.info('Invoking LLM "{}" with specified inference parameters "{}" and additional model fields "{}"...'.
                 format(os.environ['LLM_MODEL_OR_INFERENCE_PROFILE_ID'], inference_config, additional_model_fields))
    response = bedrock_rt_client.converse(
        modelId=os.environ['LLM_MODEL_OR_INFERENCE_PROFILE_ID'],
        messages=messages,
        system=system_prompts,
        inferenceConfig=inference_config,
        additionalModelRequestFields=additional_model_fields
    )
    logging.info('Completed invoking LLM.')
    prompt_response = response['output']['message']['content'][0]['text']
    # Log the prompt and it's response
    if LOG_LLM_PROCESSING_INFO:
        token_usage = response['usage']
        logging.info("Input tokens: {}".format(token_usage['inputTokens']))
        logging.info("Output tokens: {}".format(token_usage['outputTokens']))
        logging.info("Total tokens: {}".format(token_usage['totalTokens']))
        logging.info("Stop reason: {}".format(response['stopReason']))
        metrics = response['metrics']
        logging.info('Prompt latency = {} second(s)'.format(int(metrics['latencyMs']) / 1000))
        logging.info('PROMPT: {}'.format(messages[0]['content'][0]))
        logging.info('RESPONSE: {}'.format(prompt_response))
    # Return the LLM response text
    return prompt_response


# Invoke the specified boto3 API
def invoke_boto3_api(ec2_client, boto3_api_name, boto3_api_request_json):
    try:
        match boto3_api_name:
            case 'describe_volumes':
                return ec2_client.describe_volumes(**boto3_api_request_json)
            case 'describe_snapshots':
                return ec2_client.describe_snapshots(**boto3_api_request_json)
            case 'create_snapshot':
                return ec2_client.create_snapshot(**boto3_api_request_json)
            case 'delete_snapshot':
                return ec2_client.delete_snapshot(**boto3_api_request_json)
            case _:
                return {}
    except Exception as exception:
        raise exception


# Invoke boto3 APIs with LLM intervened retry
def invoke_boto3_api_with_llm_intervened_retry(aws_account_id, aws_region, ec2_client,
                                               boto3_api_name, boto3_api_request_json):
    try:
        try:
            response = invoke_boto3_api(ec2_client, boto3_api_name, boto3_api_request_json)
        except Exception as exception:
            logging.info('Error occurred when invoking boto3 API "{}" :: {}'.format(boto3_api_name, exception))
            logging.info('Fixing the boto3 API JSON request using LLM...')
            fixed_boto3_api_request_json = json.loads(process_prompt_for_boto3_api_retry(aws_account_id,
                                                                                         aws_region,
                                                                                         boto3_api_name,
                                                                                         json.dumps(boto3_api_request_json),
                                                                                         str(exception)))
            logging.info('Completed fixing the boto3 API JSON request using LLM.')
            logging.info('Retrying boto3 API "{}" after fixing the JSON request using LLM...'.format(boto3_api_name))
            response = invoke_boto3_api(ec2_client, boto3_api_name, fixed_boto3_api_request_json)
            logging.info('Completed retrying boto3 API "{}" after fixing the JSON request using LLM.'.format(boto3_api_name))
    except Exception as final_exception:
        raise final_exception
    return response


# Parse the input Lambda event received from Agents for Amazon Bedrock
def parse_request_and_prepare_response(event):
    response_body_text_list = []
    function_response_state = ''
    logging.info('Parsing request data...')
    # Get the various objects from the input event
    prompt_session_attributes = event["promptSessionAttributes"]
    session_attributes = event["sessionAttributes"]
    # Get the AWS account id from the session attributes, if it exists; if not, add to it
    if 'AWSAccountId' in session_attributes:
        aws_account_id = session_attributes['AWSAccountId']
    else:
        aws_account_id = (boto3.client('sts')).get_caller_identity().get('Account')
        session_attributes['AWSAccountId'] = aws_account_id
    # Append to the response body text
    response_body_text = 'AWS Account Id "{}" will be used.'.format(aws_account_id)
    response_body_text_list.append(response_body_text)
    logging.info(response_body_text)
    # Get the input parameters
    aws_region, backup_plan_id, boto3_api_name, boto3_api_json_text = '', '', '', ''
    input_text = event["inputText"]
    # Loop through the input parameters
    input_parameters = event["parameters"]
    for input_parameter in input_parameters:
        # Retrieve the value of the parameters
        if input_parameter["name"] == "AWSRegion":
            aws_region = input_parameter["value"]
        elif input_parameter["name"] == "Boto3APIName":
            boto3_api_name = input_parameter["value"].lower()
            boto3_api_name = substring_after(boto3_api_name, 'ec2.client.')
        elif input_parameter["name"] == "Boto3APIJSON":
            boto3_api_json_text = input_parameter["value"]
    logging.info('Completed parsing request data.')
    # Set the default AWS region if not found in the input
    if len(aws_region) == 0:
        aws_region = os.environ['DEFAULT_AWS_REGION']
    # Append to the response body text
    response_body_text = 'AWS Region "{}" will be used.'.format(aws_region)
    response_body_text_list.append(response_body_text)
    logging.info(response_body_text)
    # Instantiate the Amazon EC2 boto3 client for the specific region
    ec2_client = boto3.client('ec2', region_name=aws_region, config=get_boto_config())
    # Except for custom APIs, validate the boto3 JSON for the specified user input by invoking a LLM
    if boto3_api_name not in ('describe_volumes',
                              'describe_snapshots',
                              'describe_snapshots_for_all_instances',
                              'describe_snapshots_for_instance_ids',
                              'describe_snapshots_for_instance_names',
                              'describe_snapshots_for_instance_tags',
                              'create_snapshot',
                              'delete_snapshot'):
        logging.info('Validating the boto3 API JSON...')
        boto3_api_json_text = process_prompt(aws_account_id, aws_region, boto3_api_name, input_text, boto3_api_json_text)
        logging.info('Completed validating the boto3 API JSON.')
    # Determine the action type based on the existence of the relevant parameters
    if len(boto3_api_json_text) == 0:
        function_response_state = 'FAILURE'
        # Append to the response body text
        response_body_text = 'Boto3 API call JSON text does not exist. No API was invoked.'
        response_body_text_list.append(response_body_text)
        logging.warning(response_body_text)
    else:
        # Append to the response body text
        response_body_text = 'Boto3 API "{}" was specified.'.format(boto3_api_name)
        response_body_text_list.append(response_body_text)
        logging.info(response_body_text)
        # Process according to the API
        if boto3_api_name == 'describe_volumes':
            instance_id = ''
            # Parse the JSON
            describe_volumes_json = json.loads(boto3_api_json_text)
            # Retrieve the instance id
            describe_volumes_filters = describe_volumes_json['Filters']
            for describe_volumes_filter in describe_volumes_filters:
                if describe_volumes_filter['Name'] == 'attachment.instance-id':
                    instance_id = describe_volumes_filter['Values'][0]
            # Check the instance id and process accordingly
            if len(instance_id) > 0:
                # Check if the instance exists and process accordingly
                if does_instance_exist_for_id(ec2_client, instance_id):
                    # List the volumes attached to the instance by invoking the API
                    logging.info('Listing volumes attached to the instance...')
                    describe_volumes_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                           aws_region,
                                                                                           ec2_client,
                                                                                           'describe_volumes',
                                                                                           describe_volumes_json)
                    logging.info('Completed listing volumes attached to the instance.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'List of volumes attached to the instance id "{}" :: "{}"'
                        .format(instance_id, describe_volumes_response['Volumes']))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'The specified instance id "{}" does not exist.'.format(instance_id)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Instance id is missing. It is required to get the list of volumes attached to the instance.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_snapshots':
            volume_id = ''
            # Parse the JSON
            describe_snapshots_json = json.loads(boto3_api_json_text)
            # Retrieve the volume id
            describe_snapshots_filters = describe_snapshots_json['Filters']
            for describe_snapshots_filter in describe_snapshots_filters:
                if describe_snapshots_filter['Name'] == 'volume-id':
                    volume_id = describe_snapshots_filter['Values'][0]
            # Check the volume id and process accordingly
            if len(volume_id) > 0:
                # Check if the volume exists and process accordingly
                if does_volume_exist_for_id(ec2_client, volume_id):
                    # List the snapshots attached to the volume by invoking the API
                    logging.info('Listing snapshots attached to the volume...')
                    describe_snapshots_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                           aws_region,
                                                                                           ec2_client,
                                                                                           'describe_snapshots',
                                                                                           describe_snapshots_json)
                    logging.info('Completed listing snapshots attached to the volume.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'List of snapshots attached to the volume id "{}" :: "{}"'
                        .format(volume_id, describe_snapshots_response['Snapshots']))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'The specified volume id "{}" does not exist.'.format(volume_id)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Volume id is missing. It is required to get the list of snapshots attached to the volume.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_snapshots_for_all_instances':
            logging.info('Getting all instance ids...')
            retrieved_instance_ids = get_all_instance_ids(ec2_client)
            logging.info('Completed getting all instance ids.')
            # Get the snapshots for the retrieved instance ids
            logging.info('Getting snapshot details...')
            describe_snapshots_response = get_snapshots_for_instance_ids(ec2_client, retrieved_instance_ids)
            logging.info('Completed getting snapshot details.')
            # Append to the response body text
            response_body_text_list.append('Details of snapshots associated with all instances :: {}'
                                           .format(retrieved_instance_ids,
                                                   describe_snapshots_response))
        elif boto3_api_name in ['describe_snapshots_for_instance_ids',
                                'describe_snapshots_for_instance_names',
                                'describe_snapshots_for_instance_tags']:
            # Parse the JSON
            describe_snapshots_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the instance and process accordingly
            if boto3_api_name == 'describe_snapshots_for_instance_ids':
                # Get the instance ids
                retrieved_instance_ids = describe_snapshots_json['InstanceIds']
                if len(retrieved_instance_ids) > 0:
                    retrieved_instance_ids = retrieved_instance_ids.split(',')
                    # Get the snapshots for the retrieved instance ids
                    logging.info('Getting snapshot details...')
                    describe_snapshots_response = get_snapshots_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting snapshot details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with instance ids {} :: {}'
                                                   .format(retrieved_instance_ids,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance id is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_snapshots_for_instance_names':
                # Get the instance names
                retrieved_instance_names = describe_snapshots_json['InstanceNames']
                if len(retrieved_instance_names) > 0:
                    retrieved_instance_names = retrieved_instance_names.split(',')
                    # Get the instance ids associated with all the instances that have the matching names
                    logging.info('Getting instance ids for names "{}"...'.format(retrieved_instance_names))
                    retrieved_instance_ids = get_instance_ids_for_names(ec2_client, retrieved_instance_names)
                    logging.info('Completed getting instance ids for names.')
                    # Get the snapshots for all the retrieved instance ids
                    logging.info('Getting snapshot details...')
                    describe_snapshots_response = get_snapshots_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting snapshot details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with instance names "{}" :: {}'
                                                   .format(retrieved_instance_names,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance name is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the instance tags
                retrieved_tag_name = describe_snapshots_json['InstanceTagName']
                retrieved_tag_values = describe_snapshots_json['InstanceTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the instance ids associated with all the instances that have the matching tags
                    logging.info('Getting instance ids for tag "{}" with values {}...'.format(retrieved_tag_name,
                                                                                              retrieved_tag_values))
                    retrieved_instance_ids = get_instance_ids_for_tags(ec2_client,
                                                                       retrieved_tag_name,
                                                                       retrieved_tag_values)
                    logging.info('Completed getting instance ids for tags.')
                    # Get the snapshots for all the retrieved instance ids
                    logging.info('Getting snapshot details...')
                    describe_snapshots_response = get_snapshots_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting snapshot details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with instances with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance tag name and/or value is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'create_snapshot':
            # Parse the JSON
            create_snapshot_json = json.loads(boto3_api_json_text)
            retrieved_volume_id = create_snapshot_json['VolumeId']
            # Check the value that the user provided and process accordingly
            if len(retrieved_volume_id) > 0:
                # Create the snapshot by invoking the API
                try:
                    logging.info('Creating snapshot for volume id "{}"...'.format(retrieved_volume_id))
                    create_snapshot_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                          aws_region,
                                                                                          ec2_client,
                                                                                          'create_snapshot',
                                                                                          create_snapshot_json)
                    logging.info('Completed creating snapshot.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Created snapshot for volume id "{}" :: snapshot id = "{}" with state "{}".'
                        .format(retrieved_volume_id,
                                create_snapshot_response['SnapshotId'],
                                create_snapshot_response['State']))
                except Exception as exception:
                    function_response_state = 'FAILURE'
                    # Append to the response body text
                    response_body_text = ('Error occurred while creating snapshot for volume id "{}" :: "{}"'
                                          .format(retrieved_volume_id, exception))
                    response_body_text_list.append(response_body_text)
                    logging.error(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Volume id is missing. It is required to create the snapshot.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'delete_snapshot':
            # Parse the JSON
            delete_snapshot_json = json.loads(boto3_api_json_text)
            retrieved_snapshot_id = delete_snapshot_json['SnapshotId']
            # Check the value that the user provided and process accordingly
            if len(retrieved_snapshot_id) > 0:
                # Delete the snapshot by invoking the API
                try:
                    logging.info('Deleting snapshot with id "{}"...'.format(retrieved_snapshot_id))
                    invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                               aws_region,
                                                               ec2_client,
                                                               'delete_snapshot',
                                                               delete_snapshot_json)
                    logging.info('Completed deleting snapshot.')
                    # Append to the response body text
                    response_body_text_list.append('Deleted snapshot with id "{}".'.format(retrieved_snapshot_id))
                except Exception as exception:
                    function_response_state = 'FAILURE'
                    # Append to the response body text
                    response_body_text = ('Error occurred while deleting snapshot with id "{}" :: "{}"'
                                          .format(retrieved_snapshot_id, exception))
                    response_body_text_list.append(response_body_text)
                    logging.error(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Snapshot id is missing. It is required to delete the snapshot.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        else:
            function_response_state = 'FAILURE'
            # Append to the response body text
            response_body_text = 'API "{}" is not supported. No API invocation was performed.'.format(boto3_api_name)
            logging.warning(response_body_text)
            response_body_text_list.append(response_body_text)
    # Create the response message
    logging.info('Creating the response message...')
    # Concatenate the messages
    response_body_text = ' '.join(response_body_text_list)
    # Apply the max size limit of 25KB for an AWS Lambda response message to an Amazon Bedrock Agent
    # Truncate to 22KB with a 3KB for additional data; assuming each character is represented by 1 byte
    response_body_text = response_body_text[:22000]
    response = {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event["actionGroup"],
            "function": event["function"],
            "functionResponse": {
                #"responseState": "FAILURE | REPROMPT",
                "responseBody": {
                    'TEXT': {
                        'body': response_body_text
                    }
                }
            }
        },
        "sessionAttributes": session_attributes,
        "promptSessionAttributes": prompt_session_attributes,
    }
    # Set the function response state for FAILURE and REPROMPT scenarios
    if len(function_response_state) > 0:
        response['response']['functionResponse']['responseState'] = function_response_state
    logging.info('Completed creating the response message.')
    # Return the response
    return response


# The handler function
def lambda_handler(event,context):
    logging.info('Executing the handler() function...')
    logging.info('Request event :: {}'.format(event))
    logging.info('Request context :: {}'.format(context))
    # Parse the request data and prepare response
    return_data = parse_request_and_prepare_response(event)
    logging.info('Response :: {}'.format(return_data))
    logging.info('Completed executing the handler() function.')
    return return_data