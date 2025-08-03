"""
Copyright 2025 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
import boto3
import json
import logging
import os
from botocore.config import Config
from botocore.exceptions import ClientError


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


# Get all the db clusters
def get_all_db_clusters(rds_client):
    describe_db_clusters_response = rds_client.describe_db_clusters(
        MaxRecords=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_db_clusters_response['DBClusters']


# Get the db clusters for the specified tags
def get_db_clusters_for_tags(rds_client, tag_key, tag_values):
    retrieved_db_clusters = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    # Get all the db clusters
    db_clusters = get_all_db_clusters(rds_client)
    # Loop through the db clusters
    for db_cluster in db_clusters:
        # Get the tags
        tags = db_cluster['TagList']
        # Loop through the tags
        for tag in tags:
            # Check the tag key and value
            if (tag['Key'] == tag_key) and (tag['Value'] in tag_values):
                retrieved_db_clusters.append(db_cluster)
    return retrieved_db_clusters


# Get the db clusters for the specified names
def get_db_clusters_for_names(rds_client, cluster_names):
    return get_db_clusters_for_tags(rds_client, 'Name', cluster_names)


# Get all the db instances
def get_all_db_instances(rds_client):
    describe_db_instances_response = rds_client.describe_db_instances(
        MaxRecords=int(os.environ['BOTO3_API_MAX_RESULTS'])
    )
    return describe_db_instances_response['DBInstances']


# Get the db instances for the specified tags
def get_db_instances_for_tags(rds_client, tag_key, tag_values):
    retrieved_db_instances = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    # Get all the db instances
    db_instances = get_all_db_instances(rds_client)
    # Loop through the db instances
    for db_instance in db_instances:
        # Get the tags
        tags = db_instance['TagList']
        # Loop through the tags
        for tag in tags:
            # Check the tag key and value
            if (tag['Key'] == tag_key) and (tag['Value'] in tag_values):
                retrieved_db_instances.append(db_instance)
    return retrieved_db_instances


# Get the db instances for the specified names
def get_db_instances_for_names(rds_client, instance_names):
    return get_db_instances_for_tags(rds_client, 'Name', instance_names)


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
def invoke_boto3_api(rds_client, boto3_api_name, boto3_api_request_json):
    try:
        match boto3_api_name:
            case 'describe_db_clusters':
                return rds_client.describe_db_clusters(**boto3_api_request_json)
            case 'describe_db_instances':
                return rds_client.describe_db_instances(**boto3_api_request_json)
            case 'describe_db_cluster_automated_backups':
                return rds_client.describe_db_cluster_automated_backups(**boto3_api_request_json)
            case 'describe_db_instance_automated_backups':
                return rds_client.describe_db_instance_automated_backups(**boto3_api_request_json)
            case 'start_db_instance_automated_backups_replication':
                return rds_client.start_db_instance_automated_backups_replication(**boto3_api_request_json)
            case 'stop_db_instance_automated_backups_replication':
                return rds_client.stop_db_instance_automated_backups_replication(**boto3_api_request_json)
            case 'delete_db_cluster_automated_backup':
                return rds_client.delete_db_cluster_automated_backup(**boto3_api_request_json)
            case 'delete_db_instance_automated_backup':
                return rds_client.delete_db_instance_automated_backup(**boto3_api_request_json)
            case _:
                return {}
    except Exception as exception:
        raise exception


# Invoke boto3 APIs with LLM intervened retry
def invoke_boto3_api_with_llm_intervened_retry(aws_account_id, aws_region, rds_client,
                                               boto3_api_name, boto3_api_request_json):
    try:
        try:
            response = invoke_boto3_api(rds_client, boto3_api_name, boto3_api_request_json)
        except ClientError as e:
            if (boto3_api_name in ['start_db_instance_automated_backups_replication', 'stop_db_instance_automated_backups_replication'])\
                    and (e.response['Error']['Code'] == 'InvalidParameterValue'):
                response = {'handled_exception_message': 'The specified Source RDS db instance ARN "{}" is not a valid ARN.'.format(boto3_api_request_json['SourceDBInstanceArn'])}
            elif (boto3_api_name in ['start_db_instance_automated_backups_replication', 'stop_db_instance_automated_backups_replication'])\
                    and (e.response['Error']['Code'] == 'DBInstanceNotFound'):
                response = {'handled_exception_message': 'The specified Source RDS db instance with ARN "{}" not found.'.format(boto3_api_request_json['SourceDBInstanceArn'])}
            elif (boto3_api_name == 'delete_db_cluster_automated_backup') and (e.response['Error']['Code'] == 'InvalidParameterValue'):
                response = {'handled_exception_message': 'The specified RDS db cluster resource id "{}" is not valid.'.format(boto3_api_request_json['DbClusterResourceId'])}
            elif (boto3_api_name == 'delete_db_instance_automated_backup') and (e.response['Error']['Code'] == 'InvalidParameterValue'):
                response = {'handled_exception_message': 'The specified RDS db instance resource id "{}" is not valid.'.format(boto3_api_request_json['DbiResourceId'])}
            else:
                logging.info('Error occurred when invoking boto3 API "{}" :: {}'.format(boto3_api_name, e))
                logging.info('Fixing the boto3 API JSON request using LLM...')
                fixed_boto3_api_request_json = json.loads(process_prompt_for_boto3_api_retry(aws_account_id,
                                                                                             aws_region,
                                                                                             boto3_api_name,
                                                                                             json.dumps(boto3_api_request_json),
                                                                                             str(e)))
                logging.info('Completed fixing the boto3 API JSON request using LLM.')
                logging.info('Retrying boto3 API "{}" after fixing the JSON request using LLM...'.format(boto3_api_name))
                response = invoke_boto3_api(rds_client, boto3_api_name, fixed_boto3_api_request_json)
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
            boto3_api_name = substring_after(boto3_api_name, 'rds.client.')
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
    # Instantiate the Amazon RDS boto3 client for the specific region
    rds_client = boto3.client('rds', region_name=aws_region, config=get_boto_config())
    # Except for custom APIs, validate the boto3 JSON for the specified user input by invoking a LLM
    if boto3_api_name not in ('describe_db_clusters',
                              'describe_db_clusters_for_cluster_names',
                              'describe_db_clusters_for_cluster_tags',
                              'describe_db_instances',
                              'describe_db_instances_for_instance_names',
                              'describe_db_instances_for_instance_tags',
                              'describe_db_cluster_automated_backups',
                              'describe_db_instance_automated_backups',
                              'start_db_instance_automated_backups_replication',
                              'stop_db_instance_automated_backups_replication',
                              'delete_db_cluster_automated_backup',
                              'delete_db_instance_automated_backup'):
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
        if boto3_api_name == 'describe_db_clusters':
            # Parse the JSON
            describe_db_clusters_json = json.loads(boto3_api_json_text)
            if describe_db_clusters_json is None:
                describe_db_clusters_json = {}
            # Set the max records
            describe_db_clusters_json['MaxRecords'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Get all the RDS db clusters
            logging.info('Getting the RDS db clusters...')
            describe_db_clusters_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                       aws_region,
                                                                                       rds_client,
                                                                                       'describe_db_clusters',
                                                                                       describe_db_clusters_json)
            logging.info('Completed getting the RDS db clusters.')
            # Append to the response body text
            response_body_text_list.append('RDS db clusters in the "{}" region :: {}'
                                           .format(aws_region, describe_db_clusters_response))
        elif boto3_api_name in ['describe_db_clusters_for_cluster_names',
                                'describe_db_clusters_for_cluster_tags']:
            # Parse the JSON
            describe_db_clusters_json = json.loads(boto3_api_json_text)
            if boto3_api_name == 'describe_db_clusters_for_cluster_names':
                # Get the cluster names
                retrieved_cluster_names = describe_db_clusters_json['ClusterNames']
                if len(retrieved_cluster_names) > 0:
                    retrieved_cluster_names = retrieved_cluster_names.split(',')
                    # Get all the RDS db clusters
                    logging.info('Getting the RDS db clusters for names "{}"...'.format(retrieved_cluster_names))
                    describe_db_clusters_response = get_db_clusters_for_names(rds_client, retrieved_cluster_names)
                    logging.info('Completed getting the RDS db clusters for names.')
                    response_body_text_list.append(
                        'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    # Append to the response body text
                    response_body_text_list.append('Details of RDS db clusters associated with names {} :: {}'
                                                   .format(retrieved_cluster_names,
                                                           describe_db_clusters_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more RDS db cluster name is missing. '
                                          'It is required to get the RDS db cluster details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the db cluster tags
                retrieved_tag_name = describe_db_clusters_json['ClusterTagName']
                retrieved_tag_values = describe_db_clusters_json['ClusterTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the db clusters associated with all the specified matching tag and values
                    logging.info('Getting the RDS db clusters for tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_db_clusters_response = get_db_clusters_for_tags(rds_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting the RDS db clusters for tag with values.')
                    response_body_text_list.append(
                        'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    # Append to the response body text
                    response_body_text_list.append('Details of RDS db clusters associated with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_db_clusters_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more RDS db cluster tag name and/or value is missing. '
                                          'It is required to get the RDS db cluster details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_db_instances':
            # Parse the JSON
            describe_db_instances_json = json.loads(boto3_api_json_text)
            if describe_db_instances_json is None:
                describe_db_instances_json = {}
            # Set the max records
            describe_db_instances_json['MaxRecords'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Get all the RDS db instances
            logging.info('Getting the RDS db instances...')
            describe_db_instances_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                        aws_region,
                                                                                        rds_client,
                                                                                        'describe_db_instances',
                                                                                        describe_db_instances_json)
            logging.info('Completed getting the RDS db instances.')
            # Append to the response body text
            response_body_text_list.append('RDS db instances in the "{}" region :: {}'
                                           .format(aws_region, describe_db_instances_response))
        elif boto3_api_name in ['describe_db_instances_for_instance_names',
                                'describe_db_instances_for_instance_tags']:
            # Parse the JSON
            describe_db_instances_json = json.loads(boto3_api_json_text)
            if boto3_api_name == 'describe_db_instances_for_instance_names':
                # Get the instance names
                retrieved_instance_names = describe_db_instances_json['InstanceNames']
                if len(retrieved_instance_names) > 0:
                    retrieved_instance_names = retrieved_instance_names.split(',')
                    # Get all the RDS db instances
                    logging.info('Getting the RDS db instances for names "{}"...'.format(retrieved_instance_names))
                    describe_db_instances_response = get_db_instances_for_names(rds_client, retrieved_instance_names)
                    logging.info('Completed getting the RDS db instances for names.')
                    response_body_text_list.append(
                        'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    # Append to the response body text
                    response_body_text_list.append('Details of RDS db instances associated with names {} :: {}'
                                                   .format(retrieved_instance_names,
                                                           describe_db_instances_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more RDS db instance name is missing. '
                                          'It is required to get the RDS db instance details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                # Get the db instance tags
                retrieved_tag_name = describe_db_instances_json['InstanceTagName']
                retrieved_tag_values = describe_db_instances_json['InstanceTagValues']
                if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Get the db instances associated with all the specified matching tag and values
                    logging.info('Getting the RDS db instances for tag "{}" with values {}...'.format(retrieved_tag_name, retrieved_tag_values))
                    describe_db_instances_response = get_db_instances_for_tags(rds_client, retrieved_tag_name, retrieved_tag_values)
                    logging.info('Completed getting the RDS db instances for tag with values.')
                    response_body_text_list.append(
                        'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    # Append to the response body text
                    response_body_text_list.append('Details of RDS db instances associated with tag "{}" and with values {} :: {}'
                                                   .format(retrieved_tag_name,
                                                           retrieved_tag_values,
                                                           describe_db_instances_response))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more RDS db instance tag name and/or value is missing. '
                                          'It is required to get the RDS db instance details.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'describe_db_cluster_automated_backups':
            # Parse the JSON
            describe_db_cluster_automated_backups_json = json.loads(boto3_api_json_text)
            if describe_db_cluster_automated_backups_json is None:
                describe_db_cluster_automated_backups_json = {}
            # Set the max records
            describe_db_cluster_automated_backups_json['MaxRecords'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Get all the RDS db cluster automated backups
            logging.info('Getting the RDS db cluster automated backups...')
            describe_db_cluster_automated_backups_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                        aws_region,
                                                                                                        rds_client,
                                                                                                        'describe_db_cluster_automated_backups',
                                                                                                        describe_db_cluster_automated_backups_json)
            logging.info('Completed getting the RDS db cluster automated backups.')
            # Append to the response body text
            response_body_text_list.append('RDS db cluster automated backups in the "{}" region :: {}'
                                           .format(aws_region, describe_db_cluster_automated_backups_response))
        elif boto3_api_name == 'describe_db_instance_automated_backups':
            # Parse the JSON
            describe_db_instance_automated_backups_json = json.loads(boto3_api_json_text)
            if describe_db_instance_automated_backups_json is None:
                describe_db_instance_automated_backups_json = {}
            # Set the max records
            describe_db_instance_automated_backups_json['MaxRecords'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} records(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Get all the RDS db instance automated backups
            logging.info('Getting the RDS db instance automated backups...')
            describe_db_instance_automated_backups_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                         aws_region,
                                                                                                         rds_client,
                                                                                                         'describe_db_instance_automated_backups',
                                                                                                         describe_db_instance_automated_backups_json)
            logging.info('Completed getting the RDS db instance automated backups.')
            # Append to the response body text
            response_body_text_list.append('RDS db instance automated backups in the "{}" region :: {}'
                                           .format(aws_region, describe_db_instance_automated_backups_response))
        elif boto3_api_name == 'start_db_instance_automated_backups_replication':
            # Parse the JSON
            start_db_instance_automated_backups_replication_json = json.loads(boto3_api_json_text)
            # Get the source db instance ARN
            source_db_instance_arn = start_db_instance_automated_backups_replication_json['SourceDBInstanceArn']
            # Check the source db instance ARN and process accordingly
            if len(source_db_instance_arn) > 0:
                # Get all the RDS db instance automated backups
                logging.info('Starting the RDS db instance automated backups replication...')
                start_db_instance_automated_backups_replication_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                                      aws_region,
                                                                                                                      rds_client,
                                                                                                                      'start_db_instance_automated_backups_replication',
                                                                                                                      start_db_instance_automated_backups_replication_json)
                if 'handled_exception_message' in start_db_instance_automated_backups_replication_response:
                    # Append to the response body text
                    response_body_text_list.append(
                        start_db_instance_automated_backups_replication_response['handled_exception_message'])
                else:
                    # Append to the response body text
                    response_body_text_list.append('RDS db instance automated backups replication start status :: {}'
                                                   .format(aws_region,
                                                           start_db_instance_automated_backups_replication_response[
                                                               'DBInstanceAutomatedBackup']['Status']))
                logging.info('Completed starting the RDS db instance automated backups replication.')
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'RDS source database instance ARN is missing. It is required to start the RDS db instance automated backups replication.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'stop_db_instance_automated_backups_replication':
            # Parse the JSON
            stop_db_instance_automated_backups_replication_json = json.loads(boto3_api_json_text)
            # Get the source db instance ARN
            source_db_instance_arn = stop_db_instance_automated_backups_replication_json['SourceDBInstanceArn']
            # Check the source db instance ARN and process accordingly
            if len(source_db_instance_arn) > 0:
                # Get all the RDS db instance automated backups
                logging.info('Stopping the RDS db instance automated backups replication...')
                stop_db_instance_automated_backups_replication_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                                      aws_region,
                                                                                                                      rds_client,
                                                                                                                      'stop_db_instance_automated_backups_replication',
                                                                                                                      stop_db_instance_automated_backups_replication_json)
                if 'handled_exception_message' in stop_db_instance_automated_backups_replication_response:
                    # Append to the response body text
                    response_body_text_list.append(
                        stop_db_instance_automated_backups_replication_response['handled_exception_message'])
                else:
                    # Append to the response body text
                    response_body_text_list.append('RDS db instance automated backups replication stop status :: {}'
                                                   .format(aws_region,
                                                           stop_db_instance_automated_backups_replication_response[
                                                               'DBInstanceAutomatedBackup']['Status']))
                logging.info('Completed stopping the RDS db instance automated backups replication.')
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'RDS source database instance ARN is missing. It is required to stop the RDS db instance automated backups replication.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'delete_db_cluster_automated_backup':
            # Parse the JSON
            delete_db_cluster_automated_backup_json = json.loads(boto3_api_json_text)
            # Get the db cluster resource ID
            db_cluster_resource_id = delete_db_cluster_automated_backup_json['DbClusterResourceId']
            # Check the db cluster resource ID and process accordingly
            if len(db_cluster_resource_id) > 0:
                # Delete the RDS db cluster automated backup
                logging.info('Deleting the RDS db cluster automated backup...')
                delete_db_cluster_automated_backup_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                         aws_region,
                                                                                                         rds_client,
                                                                                                         'delete_db_cluster_automated_backup',
                                                                                                         delete_db_cluster_automated_backup_json)
                if 'handled_exception_message' in delete_db_cluster_automated_backup_response:
                    # Append to the response body text
                    response_body_text_list.append(delete_db_cluster_automated_backup_response['handled_exception_message'])
                else:
                    # Append to the response body text
                    response_body_text_list.append('RDS db instance automated backup deletion status :: {}'
                                                   .format(aws_region,
                                                           delete_db_cluster_automated_backup_response['DBClusterAutomatedBackup']['Status']))
                logging.info('Completed deleting the RDS db cluster automated backup.')
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'RDS database cluster resource id is missing. It is required to delete the RDS db cluster automated backup.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'delete_db_instance_automated_backup':
            # Parse the JSON
            delete_db_instance_automated_backup_json = json.loads(boto3_api_json_text)
            # Get the db instance resource ID
            db_instance_resource_id = delete_db_instance_automated_backup_json['DbiResourceId']
            # Check the db instance resource ID and process accordingly
            if len(db_instance_resource_id) > 0:
                # Delete the RDS db instance automated backup
                logging.info('Deleting the RDS db instance automated backup...')
                delete_db_instance_automated_backup_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                         aws_region,
                                                                                                         rds_client,
                                                                                                         'delete_db_instance_automated_backup',
                                                                                                         delete_db_instance_automated_backup_json)
                if 'handled_exception_message' in delete_db_instance_automated_backup_response:
                    # Append to the response body text
                    response_body_text_list.append(delete_db_instance_automated_backup_response['handled_exception_message'])
                else:
                    # Append to the response body text
                    response_body_text_list.append('RDS db instance automated backup deletion status :: {}'
                                                   .format(aws_region,
                                                           delete_db_instance_automated_backup_response['DBInstanceAutomatedBackup']['Status']))
                logging.info('Completed deleting the RDS db instance automated backup.')
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'RDS database instance resource id is missing. It is required to delete the RDS db instance automated backup.'
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