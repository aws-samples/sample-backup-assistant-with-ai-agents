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


# Get all the S3 bucket names (and their corresponding regions)
# from the specified regions in the current account
def get_all_s3_bucket_names_for_regions(s3_client, aws_regions):
    bucket_names_and_regions = []
    if len(aws_regions) == 0:
        list_buckets_response = s3_client.list_buckets(
            MaxBuckets=int(os.environ['BOTO3_API_MAX_RESULTS'])
        )
        buckets = list_buckets_response['Buckets']
        for bucket in buckets:
            if 'BucketRegion' in bucket:
                bucket_names_and_regions.append(
                    {
                        'name': bucket['Name'],
                        'region': bucket['BucketRegion']
                    }
                )
            else:
                bucket_names_and_regions.append(
                    {
                        'name': bucket['Name'],
                        'region': ''
                    }
                )
    else:
        # Loop through the specified regions
        for aws_region in aws_regions:
            s3_client = boto3.client('s3', region_name=aws_region, config=get_boto_config())
            list_buckets_response = s3_client.list_buckets(
                BucketRegion=aws_region,
                MaxBuckets=int(os.environ['BOTO3_API_MAX_RESULTS'])
            )
            buckets = list_buckets_response['Buckets']
            for bucket in buckets:
                bucket_names_and_regions.append(
                    {
                        'name': bucket['Name'],
                        'region': bucket['BucketRegion']
                    }
                )
    return bucket_names_and_regions


# Get all the S3 bucket names (and their corresponding regions)
# from the specified regions in the current account
def get_all_s3_bucket_names_for_regions_and_tags(s3_client, aws_regions, tag_key, tag_values):
    bucket_names_and_regions_and_tags = []
    bucket_names_and_regions = get_all_s3_bucket_names_for_regions(s3_client, aws_regions)
    for bucket_name_and_region in bucket_names_and_regions:
        bucket_name = bucket_name_and_region['name']
        try:
            get_bucket_tagging_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            # Get the tags
            tags = get_bucket_tagging_response['TagSet']
            # Loop through the tags
            for tag in tags:
                # Check the tag key and value
                if (tag['Key'] == tag_key) and (tag['Value'] in tag_values):
                    bucket_names_and_regions_and_tags.append(bucket_name_and_region)
        except ClientError as e:
            # Filter the errors caused by no tags in buckets
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                raise e
    return bucket_names_and_regions_and_tags


# Check if the specified S3 bucket exists in the specified region
def does_s3_bucket_exist_for_name(s3_client, aws_regions, bucket_name):
    # Get all the bucket names
    retrieved_bucket_names_and_regions = get_all_s3_bucket_names_for_regions(s3_client, aws_regions)
    for retrieved_bucket_names_and_region in retrieved_bucket_names_and_regions:
        if retrieved_bucket_names_and_region['name'] == bucket_name:
            return True
    return False


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
def invoke_boto3_api(s3_client, boto3_api_name, boto3_api_request_json):
    try:
        match boto3_api_name:
            case 'list_buckets':
                return s3_client.list_buckets(**boto3_api_request_json)
            case 'get_bucket_tagging':
                return s3_client.get_bucket_tagging(**boto3_api_request_json)
            case 'get_bucket_replication':
                return s3_client.get_bucket_replication(**boto3_api_request_json)
            case 'get_bucket_versioning':
                return s3_client.get_bucket_versioning(**boto3_api_request_json)
            case 'get_bucket_lifecycle_configuration':
                return s3_client.get_bucket_lifecycle_configuration(**boto3_api_request_json)
            case _:
                return {}
    except Exception as exception:
        raise exception


# Invoke boto3 APIs with LLM intervened retry
def invoke_boto3_api_with_llm_intervened_retry(aws_account_id, aws_region, s3_client,
                                               boto3_api_name, boto3_api_request_json):
    try:
        try:
            response = invoke_boto3_api(s3_client, boto3_api_name, boto3_api_request_json)
        except ClientError as e:
            if (boto3_api_name == 'get_bucket_replication') and (e.response['Error']['Code'] == 'ReplicationConfigurationNotFoundError'):
                response = {'handled_exception_message': 'No replication information found on S3 bucket named "{}".'.format(boto3_api_request_json['Bucket'])}
            elif (boto3_api_name == 'get_bucket_lifecycle_configuration') and (e.response['Error']['Code'] == 'NoSuchLifecycleConfiguration'):
                response = {'handled_exception_message': 'No lifecycle information found on S3 bucket named "{}".'.format(boto3_api_request_json['Bucket'])}
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
                response = invoke_boto3_api(s3_client, boto3_api_name, fixed_boto3_api_request_json)
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
            boto3_api_name = substring_after(boto3_api_name, 's3.client.')
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
    # Instantiate the Amazon S3 boto3 client for the specific region
    s3_client = boto3.client('s3', region_name=aws_region, config=get_boto_config())
    # Except for custom APIs, validate the boto3 JSON for the specified user input by invoking a LLM
    if boto3_api_name not in ('list_buckets_by_regions',
                              'list_buckets_by_regions_and_tags',
                              'get_bucket_replication',
                              'get_bucket_versioning',
                              'get_bucket_lifecycle_configuration'):
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
        if boto3_api_name == 'list_buckets_by_regions':
            # Parse the JSON
            list_buckets_by_regions_json = json.loads(boto3_api_json_text)
            # Get the region names; if not, assume all regions
            retrieved_region_names = list_buckets_by_regions_json['RegionNames']
            if len(retrieved_region_names) > 0:
                retrieved_region_names = retrieved_region_names.split(',')
            else:
                retrieved_region_names = []
            # Get all the S3 buckets across the specified regions
            logging.info('Getting the bucket names and their corresponding regions...')
            retrieved_bucket_names_and_regions = get_all_s3_bucket_names_for_regions(s3_client, retrieved_region_names)
            logging.info('Completed getting the bucket names and their corresponding regions.')
            # Append to the response body text
            response_body_text_list.append(
                'Results restricted to a max of {} bucket(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            response_body_text_list.append('Bucket names and their corresponding regions :: {}'
                                           .format(retrieved_bucket_names_and_regions))
        elif boto3_api_name == 'list_buckets_by_regions_and_tags':
            # Parse the JSON
            list_buckets_by_regions_and_tags_json = json.loads(boto3_api_json_text)
            # Get the region names; if not, assume all regions. Also, get the tag name and it's values
            retrieved_region_names = list_buckets_by_regions_and_tags_json['RegionNames']
            retrieved_tag_name = list_buckets_by_regions_and_tags_json['BucketTagName']
            retrieved_tag_values = list_buckets_by_regions_and_tags_json['BucketTagValues']
            # Check the tag name and process accordingly
            if len(retrieved_tag_name) == 0:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('The S3 bucket tag name has not been specified. '
                                      'It is required to get the S3 buckets.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
            else:
                # Check the tag values and process accordingly
                if len(retrieved_tag_values) == 0:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('One or more S3 bucket tag values have not been specified. '
                                          'It is required to get the S3 buckets.')
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
                else:
                    retrieved_tag_values = retrieved_tag_values.split(',')
                    # Check the region names and process accordingly
                    if len(retrieved_region_names) > 0:
                        retrieved_region_names = retrieved_region_names.split(',')
                    else:
                        retrieved_region_names = []
                    # Get all the S3 buckets across the specified regions for the matching tag name and values
                    logging.info('Getting the bucket names and their corresponding regions for tag "{}" with values {}...'
                                 .format(retrieved_tag_name, retrieved_tag_values))
                    retrieved_bucket_names_and_regions = get_all_s3_bucket_names_for_regions_and_tags(s3_client,
                                                                                                      retrieved_region_names,
                                                                                                      retrieved_tag_name,
                                                                                                      retrieved_tag_values)
                    logging.info('Completed getting the bucket names and their corresponding regions for tag with values.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'Results restricted to a max of {} bucket(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                    response_body_text_list.append('Bucket names and their corresponding regions for tag "{}" with values {} :: {}'
                                                   .format(retrieved_tag_name, retrieved_tag_values, retrieved_bucket_names_and_regions))
        elif boto3_api_name == 'get_bucket_replication':
            # Parse the JSON
            get_bucket_replication_json = json.loads(boto3_api_json_text)
            # Retrieve the bucket name
            retrieved_bucket_name = get_bucket_replication_json['Bucket']
            # Check if the bucket was specified and process accordingly
            if len(retrieved_bucket_name) > 0:
                response_body_text_list.append(
                    'Bucket name search was restricted to a max of {} bucket(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Check if the bucket exists and process accordingly
                if does_s3_bucket_exist_for_name(s3_client, [], retrieved_bucket_name):
                    # Get the bucket replication info
                    logging.info('Getting replication info on S3 bucket "{}"...'.format(retrieved_bucket_name))
                    try:
                        get_bucket_replication_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                     aws_region,
                                                                                                     s3_client,
                                                                                                     'get_bucket_replication',
                                                                                                     get_bucket_replication_json)
                        if 'handled_exception_message' in get_bucket_replication_response:
                            # Append to the response body text
                            response_body_text_list.append(get_bucket_replication_response['handled_exception_message'])
                        else:
                            # Append to the response body text
                            response_body_text_list.append(
                                'Replication information on S3 bucket named "{}" :: "{}"'
                                .format(retrieved_bucket_name, get_bucket_replication_response['ReplicationConfiguration']))
                    except Exception as exception:
                        function_response_state = 'FAILURE'
                        # Append to the response body text
                        response_body_text = ('Error occurred while getting the replication information on S3 bucket "{}" :: "{}"'
                                              .format(retrieved_bucket_name, exception))
                        response_body_text_list.append(response_body_text)
                        logging.error(response_body_text)
                    logging.info('Completed getting replication info on S3 bucket.')
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'The specified S3 bucket "{}" does not exist.'.format(retrieved_bucket_name)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Bucket name is missing. It is required to get the bucket replication information.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'get_bucket_versioning':
            # Parse the JSON
            get_bucket_versioning_json = json.loads(boto3_api_json_text)
            # Retrieve the bucket name
            retrieved_bucket_name = get_bucket_versioning_json['Bucket']
            # Check if the bucket was specified and process accordingly
            if len(retrieved_bucket_name) > 0:
                response_body_text_list.append(
                    'Bucket name search was restricted to a max of {} bucket(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Check if the bucket exists and process accordingly
                if does_s3_bucket_exist_for_name(s3_client, [], retrieved_bucket_name):
                    # Get the bucket versioning info
                    logging.info('Getting versioning info on S3 bucket "{}"...'.format(retrieved_bucket_name))
                    try:
                        get_bucket_versioning_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                    aws_region,
                                                                                                    s3_client,
                                                                                                    'get_bucket_versioning',
                                                                                                    get_bucket_versioning_json)
                        if 'Status' in get_bucket_versioning_response:
                            # Append to the response body text
                            response_body_text_list.append('Versioning status on S3 bucket named "{}" :: "{}"'
                                                           .format(retrieved_bucket_name, get_bucket_versioning_response['Status']))
                        else:
                            # Append to the response body text
                            response_body_text_list.append('Versioning not enabled on S3 bucket named "{}"'.format(retrieved_bucket_name))
                    except Exception as exception:
                        function_response_state = 'FAILURE'
                        # Append to the response body text
                        response_body_text = ('Error occurred while getting the versioning information on S3 bucket "{}" :: "{}"'
                                              .format(retrieved_bucket_name, exception))
                        response_body_text_list.append(response_body_text)
                        logging.error(response_body_text)
                    logging.info('Completed getting versioning info on S3 bucket.')
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'The specified S3 bucket "{}" does not exist.'.format(retrieved_bucket_name)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Bucket name is missing. It is required to get the bucket versioning information.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'get_bucket_lifecycle_configuration':
            # Parse the JSON
            get_bucket_lifecycle_configuration_json = json.loads(boto3_api_json_text)
            # Retrieve the bucket name
            retrieved_bucket_name = get_bucket_lifecycle_configuration_json['Bucket']
            # Check if the bucket was specified and process accordingly
            if len(retrieved_bucket_name) > 0:
                response_body_text_list.append(
                    'Bucket name search was restricted to a max of {} bucket(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Check if the bucket exists and process accordingly
                if does_s3_bucket_exist_for_name(s3_client, [], retrieved_bucket_name):
                    # Get the bucket lifecycle configuration info
                    logging.info('Getting lifecycle configuration info on S3 bucket "{}"...'.format(retrieved_bucket_name))
                    try:
                        get_bucket_lifecycle_configuration_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                                 aws_region,
                                                                                                                 s3_client,
                                                                                                                 'get_bucket_lifecycle_configuration',
                                                                                                                 get_bucket_lifecycle_configuration_json)
                        if 'handled_exception_message' in get_bucket_lifecycle_configuration_response:
                            # Append to the response body text
                            response_body_text_list.append(get_bucket_lifecycle_configuration_response['handled_exception_message'])
                        else:
                            # Append to the response body text
                            response_body_text_list.append(
                                'Lifecycle configuration on S3 bucket named "{}" :: "{}"'
                                .format(retrieved_bucket_name, get_bucket_lifecycle_configuration_response))
                    except Exception as exception:
                        function_response_state = 'FAILURE'
                        # Append to the response body text
                        response_body_text = ('Error occurred while getting the lifecycle configuration information on S3 bucket "{}" :: "{}"'
                                              .format(retrieved_bucket_name, exception))
                        response_body_text_list.append(response_body_text)
                        logging.error(response_body_text)
                    logging.info('Completed getting lifecycle configuration info on S3 bucket.')
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'The specified S3 bucket "{}" does not exist.'.format(retrieved_bucket_name)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Bucket name is missing. It is required to get the bucket lifecycle configuration information.'
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