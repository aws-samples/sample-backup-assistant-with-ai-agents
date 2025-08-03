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


# Get all the instances
def get_all_instances(ec2_client):
    instances = []
    describe_instances_response = ec2_client.describe_instances(
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    reservations = describe_instances_response['Reservations']
    for reservation in reservations:
        instances.extend(reservation['Instances'])
    return instances


# Get the instances for the specified ids
def get_instances_for_instance_ids(ec2_client, instance_ids):
    instances = []
    # Strip each item in the instance id list
    instance_ids = [instance_id.strip() for instance_id in instance_ids]
    # Get the instance details for the specified instance ids
    describe_instances_response = ec2_client.describe_instances(InstanceIds=instance_ids)
    reservations = describe_instances_response['Reservations']
    for reservation in reservations:
        instances.extend(reservation['Instances'])
    return instances


# Get the instances for the specified tags
def get_instances_for_tags(ec2_client, tag_key, tag_values):
    instances = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    # Get the instance details for the tag key and values
    describe_instances_response = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'tag:{}'.format(tag_key),
                'Values': tag_values
            }
        ],
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    reservations = describe_instances_response['Reservations']
    for reservation in reservations:
        instances.extend(reservation['Instances'])
    return instances


# Get the instances for the specified names
def get_instances_for_names(ec2_client, instance_names):
    return get_instances_for_tags(ec2_client, 'Name', instance_names)


# Get the instance ids for the specified tags
def get_instance_ids_for_tags(ec2_client, tag_key, tag_values):
    instance_ids = []
    # Get all the instances with matching tag and values
    instances = get_instances_for_tags(ec2_client, tag_key, tag_values)
    # Loop through and get the instance id
    for instance in instances:
        instance_ids.append(instance['InstanceId'])
    return instance_ids


# Get the instance ids for the specified names
def get_instance_ids_for_names(ec2_client, instance_names):
    return get_instance_ids_for_tags(ec2_client, 'Name', instance_names)


# Get all the volumes
def get_all_volumes(ec2_client):
    describe_volumes_response = ec2_client.describe_volumes(
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_volumes_response['Volumes']


# Get the volumes associated with the specified volume ids
def get_volumes_for_volume_ids(ec2_client, volume_ids):
    # Strip each item in the volume id list
    volume_ids = [volume_id.strip() for volume_id in volume_ids]
    # Get the volumes for the volume ids
    describe_volumes_response = ec2_client.describe_volumes(VolumeIds=volume_ids)
    return describe_volumes_response['Volumes']


# Get the volumes for the specified tags
def get_volumes_for_volume_tags(ec2_client, tag_key, tag_values):
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    # Get the volume details for the tag key and values
    describe_volumes_response = ec2_client.describe_volumes(
        Filters=[
            {
                'Name': 'tag:{}'.format(tag_key),
                'Values': tag_values
            }
        ],
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_volumes_response['Volumes']


# Get the volumes for the specified names
def get_volumes_for_volume_names(ec2_client, volume_names):
    return get_volumes_for_volume_tags(ec2_client, 'Name', volume_names)


# Get the volumes associated with the specified instance ids
def get_volumes_for_instance_ids(ec2_client, instance_ids):
    # Strip each item in the instance id list
    instance_ids = [instance_id.strip() for instance_id in instance_ids]
    # Get the volumes for the instance ids
    describe_volumes_response = ec2_client.describe_volumes(
        Filters=[
            {
                'Name': 'attachment.instance-id',
                'Values': instance_ids
            }
        ]
    )
    return describe_volumes_response['Volumes']


# Get all the snapshots
def get_all_snapshots(ec2_client):
    describe_snapshots_response = ec2_client.describe_snapshots(
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_snapshots_response['Snapshots']


# Get the snapshots associated with the specified snapshot ids
def get_snapshots_for_snapshot_ids(ec2_client, snapshot_ids):
    # Strip each item in the snapshot id list
    snapshot_ids = [snapshot_id.strip() for snapshot_id in snapshot_ids]
    # Get the snapshots for the snapshot ids
    describe_snapshots_response = ec2_client.describe_snapshots(SnapshotIds=snapshot_ids)
    return describe_snapshots_response['Snapshots']


# Get the snapshots for the specified tags
def get_snapshots_for_snapshot_tags(ec2_client, tag_key, tag_values):
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    # Get the snapshot details for the tag key and values
    describe_snapshots_response = ec2_client.describe_snapshots(
        Filters=[
            {
                'Name': 'tag:{}'.format(tag_key),
                'Values': tag_values
            }
        ],
        MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_snapshots_response['Snapshots']


# Get the snapshots for the specified names
def get_snapshots_for_snapshot_names(ec2_client, snapshot_names):
    return get_snapshots_for_snapshot_tags(ec2_client, 'Name', snapshot_names)


# Get the snapshots associated with the specified volume ids
def get_snapshots_for_volume_ids(ec2_client, volume_ids):
    # Strip each item in the volume id list
    volume_ids = [volume_id.strip() for volume_id in volume_ids]
    # Get the snapshots for the volume ids
    describe_snapshots_response = ec2_client.describe_snapshots(
        Filters=[
            {
                'Name': 'volume-id',
                'Values': volume_ids
            }
        ],
        OwnerIds=['self']  # Filter for snapshots owned by your account
    )
    return describe_snapshots_response['Snapshots']


# Get the snapshots associated with volumes with the specified tags
def get_snapshots_for_volume_tags(ec2_client, tag_key, tag_values):
    volume_ids = []
    # Get the volumes for the volume tags
    volumes = get_volumes_for_volume_tags(ec2_client, tag_key, tag_values)
    # Loop through the volumes
    for volume in volumes:
        volume_ids.append(volume['VolumeId'])
    # Get the snapshots for the volume ids
    return get_snapshots_for_volume_ids(ec2_client, volume_ids)


# Get the snapshots associated with volumes with the specified names
def get_snapshots_for_volume_names(ec2_client, volume_names):
    return get_snapshots_for_volume_tags(ec2_client, 'Name', volume_names)


# Get the snapshots associated with the specified instance ids
def get_snapshots_for_instance_ids(ec2_client, instance_ids):
    # Get the volumes for the instance ids
    volumes = get_volumes_for_instance_ids(ec2_client, instance_ids)
    # Get the volume ids
    volume_ids = [volume['VolumeId'] for volume in volumes]
    # Get the snapshots for the volume ids
    return get_snapshots_for_volume_ids(ec2_client, volume_ids)


# Get the snapshots associated with instances with the specified tags
def get_snapshots_for_instance_tags(ec2_client, tag_key, tag_values):
    return get_snapshots_for_instance_ids(ec2_client, get_instance_ids_for_tags(ec2_client, tag_key, tag_values))


# Get the snapshots associated with instances with the specified names
def get_snapshots_for_instance_names(ec2_client, volume_names):
    return get_snapshots_for_instance_tags(ec2_client, 'Name', volume_names)


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
            case 'describe_instances':
                return ec2_client.describe_instances(**boto3_api_request_json)
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
    if boto3_api_name not in ('describe_instances_for_all_instances',
                              'describe_instances_for_instance_ids',
                              'describe_instances_for_instance_names',
                              'describe_instances_for_instance_tags',
                              'describe_volumes_for_all_volumes',
                              'describe_volumes_for_instance_ids',
                              'describe_volumes_for_instance_names',
                              'describe_volumes_for_instance_tags',
                              'describe_volumes_for_volume_ids',
                              'describe_volumes_for_volume_names',
                              'describe_volumes_for_volume_tags',
                              'describe_snapshots_for_all_snapshots',
                              'describe_snapshots_for_instance_ids',
                              'describe_snapshots_for_instance_names',
                              'describe_snapshots_for_instance_tags',
                              'describe_snapshots_for_snapshot_ids',
                              'describe_snapshots_for_snapshot_names',
                              'describe_snapshots_for_snapshot_tags',
                              'describe_snapshots_for_volume_ids',
                              'describe_snapshots_for_volume_names',
                              'describe_snapshots_for_volume_tags',
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
        if boto3_api_name == 'describe_instances_for_all_instances':
            # Get all the instances
            logging.info('Getting details of all instances...')
            describe_instances_response = get_all_instances(ec2_client)
            logging.info('Completed getting details of all instances.')
            # Append to the response body text
            response_body_text_list.append(
                'Results restricted to a max of {} instance(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            response_body_text_list.append('Details of all instances :: {}'.format(describe_instances_response))
        elif boto3_api_name in ['describe_instances_for_instance_ids',
                                'describe_instances_for_instance_names',
                                'describe_instances_for_instance_tags']:
            # Parse the JSON
            describe_instances_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the instance and process accordingly
            if boto3_api_name == 'describe_instances_for_instance_ids':
                # Get the instance ids
                retrieved_instance_ids = describe_instances_json['InstanceIds']
                if len(retrieved_instance_ids) > 0:
                    retrieved_instance_ids = retrieved_instance_ids.split(',')
                    # Get the instances for the retrieved instance ids
                    logging.info('Getting instance details...')
                    describe_instances_response = get_instances_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting instance details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of instances associated with instance ids {} :: {}'
                                                   .format(retrieved_instance_ids,
                                                           describe_instances_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance id is missing. '
                                          'It is required to get the instance details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_instances_for_instance_names':
                # Get the instance names
                retrieved_instance_names = describe_instances_json['InstanceNames']
                if len(retrieved_instance_names) > 0:
                    retrieved_instance_names = retrieved_instance_names.split(',')
                    # Get the instances associated with all the specified matching names
                    logging.info('Getting instance details for for names "{}"...'.format(retrieved_instance_names))
                    describe_instances_response = get_instances_for_names(ec2_client, retrieved_instance_names)
                    logging.info('Completed getting instance details for names.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} instance(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Details of instances associated with instance names "{}" :: {}'
                                                   .format(retrieved_instance_names,
                                                           describe_instances_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance name is missing. '
                                          'It is required to get the instance details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the instance tags
                retrieved_tag_name = describe_instances_json['InstanceTagName']
                retrieved_tag_values = describe_instances_json['InstanceTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the instances associated with all the specified matching tag and values
                    logging.info('Getting instance details for tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_instances_response = get_instances_for_tags(ec2_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting instance details for tag and values.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} instance(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Details of instances associated with instances with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_instances_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance tag name and/or value is missing. '
                                          'It is required to get the instance details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_volumes_for_all_volumes':
            # Get all the volumes
            logging.info('Getting details of all volumes...')
            describe_volumes_response = get_all_volumes(ec2_client)
            logging.info('Completed getting details of all volumes.')
            # Append to the response body text
            response_body_text_list.append(
                'Results restricted to a max of {} item(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            response_body_text_list.append('Details of all the volumes :: {}'.format(describe_volumes_response))
        elif boto3_api_name in ['describe_volumes_for_instance_ids',
                                'describe_volumes_for_instance_names',
                                'describe_volumes_for_instance_tags']:
            # Parse the JSON
            describe_volumes_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the instance and process accordingly
            if boto3_api_name == 'describe_volumes_for_instance_ids':
                # Get the instance ids
                retrieved_instance_ids = describe_volumes_json['InstanceIds']
                if len(retrieved_instance_ids) > 0:
                    retrieved_instance_ids = retrieved_instance_ids.split(',')
                    # Get the volumes for the retrieved instance ids
                    logging.info('Getting volume details...')
                    describe_volumes_response = get_volumes_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting volume details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of volumes associated with instance ids {} :: {}'
                                                   .format(retrieved_instance_ids,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance id is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_volumes_for_instance_names':
                # Get the instance names
                retrieved_instance_names = describe_volumes_json['InstanceNames']
                if len(retrieved_instance_names) > 0:
                    retrieved_instance_names = retrieved_instance_names.split(',')
                    # Get the instance ids associated with all the instances that have the matching names
                    logging.info('Getting instance ids for names "{}"...'.format(retrieved_instance_names))
                    retrieved_instance_ids = get_instance_ids_for_names(ec2_client, retrieved_instance_names)
                    logging.info('Completed getting instance ids for names.')
                    # Get the volumes for all the retrieved instance ids
                    logging.info('Getting volume details...')
                    describe_volumes_response = get_volumes_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting volume details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of volumes associated with instance names "{}" :: {}'
                                                   .format(retrieved_instance_names,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance name is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the instance tags
                retrieved_tag_name = describe_volumes_json['InstanceTagName']
                retrieved_tag_values = describe_volumes_json['InstanceTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the instance ids associated with all the instances that have the matching tags
                    logging.info('Getting instance ids for tag "{}" with values {}...'.format(retrieved_tag_name,
                                                                                              retrieved_tag_values))
                    retrieved_instance_ids = get_instance_ids_for_tags(ec2_client,
                                                                       retrieved_tag_name,
                                                                       retrieved_tag_values)
                    logging.info('Completed getting instance ids for tag and values.')
                    # Get the volumes for all the retrieved instance ids
                    logging.info('Getting volume details...')
                    describe_volumes_response = get_volumes_for_instance_ids(ec2_client, retrieved_instance_ids)
                    logging.info('Completed getting volume details.')
                    # Append to the response body text
                    response_body_text_list.append('Details of volumes associated with instances with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more instance tag name and/or value is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['describe_volumes_for_volume_ids',
                                'describe_volumes_for_volume_names',
                                'describe_volumes_for_volume_tags']:
            # Parse the JSON
            describe_volumes_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the volume and process accordingly
            if boto3_api_name == 'describe_volumes_for_volume_ids':
                # Get the volume ids
                retrieved_volume_ids = describe_volumes_json['VolumeIds']
                if len(retrieved_volume_ids) > 0:
                    retrieved_volume_ids = retrieved_volume_ids.split(',')
                    # Get the volumes for the retrieved volume ids
                    logging.info('Getting volume details for volume ids "{}"...'.format(retrieved_volume_ids))
                    describe_volumes_response = get_volumes_for_volume_ids(ec2_client, retrieved_volume_ids)
                    logging.info('Completed getting volume details for volume ids.')
                    # Append to the response body text
                    response_body_text_list.append('Details of volumes associated with volume ids {} :: {}'
                                                   .format(retrieved_volume_ids,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume id is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_volumes_for_volume_names':
                # Get the volume names
                retrieved_volume_names = describe_volumes_json['VolumeNames']
                if len(retrieved_volume_names) > 0:
                    retrieved_volume_names = retrieved_volume_names.split(',')
                    # Get the volumes for the retrieved volume names
                    logging.info('Getting volume details for volume names "{}"...'.format(retrieved_volume_names))
                    describe_volumes_response = get_volumes_for_volume_names(ec2_client, retrieved_volume_names)
                    logging.info('Completed getting volume details for volume names.')
                    # Append to the response body text
                    response_body_text_list.append('Details of volumes associated with volume names {} :: {}'
                                                   .format(retrieved_volume_names,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume name is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the volume tags
                retrieved_tag_name = describe_volumes_json['VolumeTagName']
                retrieved_tag_values = describe_volumes_json['VolumeTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the volumes associated with all the specified matching tag and values
                    logging.info('Getting volume details for tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_volumes_response = get_volumes_for_volume_tags(ec2_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting volume details for tag and values.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} volume(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Details of volumes associated with volumes with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_volumes_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume tag name and/or value is missing. '
                                          'It is required to get the volume details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_snapshots_for_all_snapshots':
            # Get all the snapshots
            logging.info('Getting details of all snapshots...')
            describe_snapshots_response = get_all_snapshots(ec2_client)
            logging.info('Completed getting details of all snapshots.')
            # Append to the response body text
            response_body_text_list.append(
                'Results restricted to a max of {} item(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            response_body_text_list.append('Details of all the snapshots :: {}'.format(describe_snapshots_response))
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
                    # Get the snapshots for all the retrieved instance names
                    logging.info('Getting snapshot details for instances with names "{}"...'.format(retrieved_instance_names))
                    describe_snapshots_response = get_snapshots_for_instance_names(ec2_client, retrieved_instance_names)
                    logging.info('Completed getting snapshot details for instances with names.')
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
                    # Get the snapshots for all the instances that have the matching tags
                    logging.info('Getting snapshot details for instances with tag "{}" and values {}...'.format(retrieved_tag_name,
                                                                                                                retrieved_tag_values))
                    describe_snapshots_response = get_snapshots_for_instance_tags(ec2_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting snapshot details for instances with tag and values.')
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
        elif boto3_api_name in ['describe_snapshots_for_snapshot_ids',
                                'describe_snapshots_for_snapshot_names',
                                'describe_snapshots_for_snapshot_tags']:
            # Parse the JSON
            describe_snapshots_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the snapshot and process accordingly
            if boto3_api_name == 'describe_snapshots_for_snapshot_ids':
                # Get the snapshot ids
                retrieved_snapshot_ids = describe_snapshots_json['SnapshotIds']
                if len(retrieved_snapshot_ids) > 0:
                    retrieved_snapshot_ids = retrieved_snapshot_ids.split(',')
                    # Get the snapshots for the retrieved snapshot ids
                    logging.info('Getting snapshot details for snapshot ids "{}"...'.format(retrieved_snapshot_ids))
                    describe_snapshots_response = get_snapshots_for_snapshot_ids(ec2_client, retrieved_snapshot_ids)
                    logging.info('Completed getting snapshot details for snapshot ids.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with snapshot ids {} :: {}'
                                                   .format(retrieved_snapshot_ids,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more snapshot id is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_snapshots_for_snapshot_names':
                # Get the snapshot names
                retrieved_snapshot_names = describe_snapshots_json['SnapshotNames']
                if len(retrieved_snapshot_names) > 0:
                    retrieved_snapshot_names = retrieved_snapshot_names.split(',')
                    # Get the snapshots for the retrieved snapshot names
                    logging.info('Getting snapshot details for snapshot names "{}"...'.format(retrieved_snapshot_names))
                    describe_snapshots_response = get_snapshots_for_snapshot_names(ec2_client, retrieved_snapshot_names)
                    logging.info('Completed getting snapshot details for snapshot names.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with snapshot names {} :: {}'
                                                   .format(retrieved_snapshot_names,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more snapshot name is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the snapshot tags
                retrieved_tag_name = describe_snapshots_json['SnapshotTagName']
                retrieved_tag_values = describe_snapshots_json['SnapshotTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the snapshots associated with all the specified matching tag and values
                    logging.info('Getting snapshot details for tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_snapshots_response = get_snapshots_for_snapshot_tags(ec2_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting snapshot details for tag with values.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} snapshot(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Details of snapshots associated with snapshots with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more snapshot tag name and/or value is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['describe_snapshots_for_volume_ids',
                                'describe_snapshots_for_volume_names',
                                'describe_snapshots_for_volume_tags']:
            # Parse the JSON
            describe_snapshots_json = json.loads(boto3_api_json_text)
            # Check if the user provided the id of the volume and process accordingly
            if boto3_api_name == 'describe_snapshots_for_volume_ids':
                # Get the volume ids
                retrieved_volume_ids = describe_snapshots_json['VolumeIds']
                if len(retrieved_volume_ids) > 0:
                    retrieved_volume_ids = retrieved_volume_ids.split(',')
                    # Get the snapshots for the retrieved volume ids
                    logging.info('Getting snapshot details for volume ids "{}"...'.format(retrieved_volume_ids))
                    describe_snapshots_response = get_snapshots_for_volume_ids(ec2_client, retrieved_volume_ids)
                    logging.info('Completed getting snapshot details for volume ids.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with volume ids {} :: {}'
                                                   .format(retrieved_volume_ids,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume id is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif boto3_api_name == 'describe_snapshots_for_volume_names':
                # Get the snapshot names
                retrieved_volume_names = describe_snapshots_json['VolumeNames']
                if len(retrieved_volume_names) > 0:
                    retrieved_volume_names = retrieved_volume_names.split(',')
                    # Get the snapshots for the retrieved volume names
                    logging.info('Getting snapshot details for volume names "{}"...'.format(retrieved_volume_names))
                    describe_snapshots_response = get_snapshots_for_volume_names(ec2_client, retrieved_volume_names)
                    logging.info('Completed getting snapshot details for volume names.')
                    # Append to the response body text
                    response_body_text_list.append('Details of snapshots associated with volume names {} :: {}'
                                                   .format(retrieved_volume_names,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume name is missing. '
                                          'It is required to get the snapshot details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the volume tags
                retrieved_tag_name = describe_snapshots_json['VolumeTagName']
                retrieved_tag_values = describe_snapshots_json['VolumeTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the snapshots associated with all the specified matching volume tag and values
                    logging.info('Getting snapshot details for volume tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_snapshots_response = get_snapshots_for_volume_tags(ec2_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting snapshot details for volume tag with values.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} snapshot(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Details of snapshots associated with volumes with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_snapshots_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more volume tag name and/or value is missing. '
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