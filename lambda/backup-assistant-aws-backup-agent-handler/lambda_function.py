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


# Check if the backup vault for the specified name exists;
# # If it exists, also return the backup vault ARN
def does_backup_vault_exist_for_name(bkp_client, backup_vault_name):
    backup_vaults = (bkp_client.list_backup_vaults(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['BackupVaultList']
    for backup_vault in backup_vaults:
        if backup_vault['BackupVaultName'] == backup_vault_name:
            return True, backup_vault['BackupVaultArn']
    return False, ''


# Get the backup vault details for the specified name
def get_backup_vault_for_name(bkp_client, backup_vault_name):
    backup_vaults = (bkp_client.list_backup_vaults(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['BackupVaultList']
    for backup_vault in backup_vaults:
        if backup_vault['BackupVaultName'] == backup_vault_name:
            return True, backup_vault
    return False, None


# Get the backup vault details for the specified ARN
def get_backup_vault_for_arn(bkp_client, backup_vault_arn):
    backup_vaults = (bkp_client.list_backup_vaults(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['BackupVaultList']
    for backup_vault in backup_vaults:
        if backup_vault['BackupVaultArn'] == backup_vault_arn:
            return True, backup_vault
    return False, None


# List the backup vault details for the specified tag and values
def list_backup_vaults_for_tags(bkp_client, tag_key, tag_values):
    retrieved_backup_vaults = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    backup_vaults = (bkp_client.list_backup_vaults(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['BackupVaultList']
    for backup_vault in backup_vaults:
        backup_vault_arn = backup_vault['BackupVaultArn']
        retrieved_tags = (bkp_client.list_tags(ResourceArn=backup_vault_arn, MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['Tags']
        retrieved_tag_keys = retrieved_tags.keys()
        for retrieved_tag_key in retrieved_tag_keys:
            if (retrieved_tag_key == tag_key) and (retrieved_tags[retrieved_tag_key] in tag_values):
                retrieved_backup_vaults.append(backup_vault)
    return retrieved_backup_vaults


# Check and create backup vault
def check_and_create_backup_vault(bkp_client, backup_vault_name, response_body_text_list):
    if len(backup_vault_name) == 0:
        response_body_text = 'Backup vault name not specified.'
        response_body_text_list.append(response_body_text)
        logging.warning(response_body_text)
    else:
        # Check if the backup vault exists and process accordingly
        backup_vault_exists, retrieved_backup_vault_details = get_backup_vault_for_name(bkp_client, backup_vault_name)
        if backup_vault_exists:
            response_body_text = ('Backup vault named "{}" exists.'.format(backup_vault_name))
            response_body_text_list.append(response_body_text)
            logging.info(response_body_text)
        else:
            # Create the backup vault
            logging.info('Creating backup vault named "{}"...')
            create_backup_vault_response = bkp_client.create_backup_vault(BackupVaultName=backup_vault_name)
            logging.info('Created backup vault named "{}".')
            response_body_text = ('Backup vault named "{}" created. Its ARN is "{}".'.format(backup_vault_name,
                                                                                             create_backup_vault_response['BackupVaultArn']))
            response_body_text_list.append(response_body_text)
            logging.info(response_body_text)


# Check if the backup plan for the specified id exists;
# If it exists, also return the backup plan name
def does_backup_plan_exist_for_id(bkp_client, backup_plan_id):
    backup_plans = (bkp_client.list_backup_plans(IncludeDeleted=False))['BackupPlansList']
    for backup_plan in backup_plans:
        if backup_plan['BackupPlanId'] == backup_plan_id:
            return True, backup_plan['BackupPlanName']
    return False, ''


# Check if the backup plan for the specified name exists;
# If it exists, also return the backup plan id
def does_backup_plan_exist_for_name(bkp_client, backup_plan_name):
    backup_plans = (bkp_client.list_backup_plans(IncludeDeleted=False))['BackupPlansList']
    for backup_plan in backup_plans:
        if backup_plan['BackupPlanName'] == backup_plan_name:
            return True, backup_plan['BackupPlanId']
    return False, ''


# Check if the specified backup selection for the id exists;
# If it exists, also return the backup selection name
def does_backup_selection_exist_for_id(bkp_client, backup_plan_id, backup_selection_id):
    backup_selections = (bkp_client.list_backup_selections(BackupPlanId=backup_plan_id))['BackupSelectionsList']
    for backup_selection in backup_selections:
        if backup_selection['SelectionId'] == backup_selection_id:
            return True, backup_selection['SelectionName']
    return False, ''


# List the backup plan details for the specified tag and values
def list_backup_plans_for_tags(bkp_client, tag_key, tag_values):
    retrieved_backup_plans = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    backup_plans = (bkp_client.list_backup_plans(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['BackupPlansList']
    for backup_plan in backup_plans:
        backup_plan_arn = backup_plan['BackupPlanArn']
        retrieved_tags = (bkp_client.list_tags(ResourceArn=backup_plan_arn, MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['Tags']
        retrieved_tag_keys = retrieved_tags.keys()
        for retrieved_tag_key in retrieved_tag_keys:
            if (retrieved_tag_key == tag_key) and (retrieved_tags[retrieved_tag_key] in tag_values):
                retrieved_backup_plans.append(backup_plan)
    return retrieved_backup_plans


# Check if the specified backup selection for the name exists;
# If it exists, also return the backup selection id
def does_backup_selection_exist_for_name(bkp_client, backup_plan_id, backup_selection_name):
    backup_selections = (bkp_client.list_backup_selections(BackupPlanId=backup_plan_id))['BackupSelectionsList']
    for backup_selection in backup_selections:
        if backup_selection['SelectionName'] == backup_selection_name:
            return True, backup_selection['SelectionId']
    return False, ''


# Check if the legal hold for the specified id exists;
# # If it exists, also return the legal hold ARN
def does_legal_hold_exist_for_id(bkp_client, legal_hold_id):
    legal_holds = (bkp_client.list_legal_holds())['LegalHolds']
    for legal_hold in legal_holds:
        if legal_hold['LegalHoldId'] == legal_hold_id:
            return True, legal_hold['LegalHoldArn']
    return False, ''


# Check if the legal hold for the specified ARN exists;
# # If it exists, also return the legal hold id
def does_legal_hold_exist_for_arn(bkp_client, legal_hold_arn):
    legal_holds = (bkp_client.list_legal_holds())['LegalHolds']
    for legal_hold in legal_holds:
        if legal_hold['LegalHoldArn'] == legal_hold_arn:
            return True, legal_hold['LegalHoldId']
    return False, ''


# List the legal hold details for the specified tag and values
def list_legal_holds_for_tags(bkp_client, tag_key, tag_values):
    retrieved_legal_holds = []
    # Strip each item in the tag values list
    tag_values = [tag_value.strip() for tag_value in tag_values]
    legal_holds = (bkp_client.list_legal_holds(MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['LegalHolds']
    for legal_hold in legal_holds:
        legal_hold_arn = legal_hold['LegalHoldArn']
        retrieved_tags = (bkp_client.list_tags(ResourceArn=legal_hold_arn, MaxResults=int(os.environ['BOTO3_API_MAX_RESULTS'])))['Tags']
        retrieved_tag_keys = retrieved_tags.keys()
        for retrieved_tag_key in retrieved_tag_keys:
            if (retrieved_tag_key == tag_key) and (retrieved_tags[retrieved_tag_key] in tag_values):
                retrieved_legal_holds.append(legal_hold)
    return retrieved_legal_holds


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
def invoke_boto3_api(bkp_client, boto3_api_name, boto3_api_request_json):
    try:
        match boto3_api_name:
            case 'create_backup_vault':
                return bkp_client.create_backup_vault(**boto3_api_request_json)
            case 'create_logically_air_gapped_backup_vault':
                return bkp_client.create_logically_air_gapped_backup_vault(**boto3_api_request_json)
            case 'create_backup_plan':
                return bkp_client.create_backup_plan(**boto3_api_request_json)
            case 'update_backup_plan':
                return bkp_client.update_backup_plan(**boto3_api_request_json)
            case 'create_backup_selection':
                return bkp_client.create_backup_selection(**boto3_api_request_json)
            case 'list_backup_vaults':
                return bkp_client.list_backup_vaults(**boto3_api_request_json)
            case 'list_protected_resources':
                return bkp_client.list_protected_resources(**boto3_api_request_json)
            case 'list_protected_resources_by_backup_vault':
                return bkp_client.list_protected_resources_by_backup_vault(**boto3_api_request_json)
            case 'list_backup_jobs':
                return bkp_client.list_backup_jobs(**boto3_api_request_json)
            case 'list_backup_plans':
                return bkp_client.list_backup_plans(**boto3_api_request_json)
            case 'list_backup_selections':
                return bkp_client.list_backup_selections(**boto3_api_request_json)
            case 'get_backup_plan':
                return bkp_client.get_backup_plan(**boto3_api_request_json)
            case 'get_backup_selection':
                return bkp_client.get_backup_selection(**boto3_api_request_json)
            case 'delete_backup_plan':
                return bkp_client.delete_backup_plan(**boto3_api_request_json)
            case 'delete_backup_selection':
                return bkp_client.delete_backup_selection(**boto3_api_request_json)
            case 'create_legal_hold':
                return bkp_client.create_legal_hold(**boto3_api_request_json)
            case 'list_legal_holds':
                return bkp_client.list_legal_holds(**boto3_api_request_json)
            case 'get_legal_hold':
                return bkp_client.get_legal_hold(**boto3_api_request_json)
            case 'cancel_legal_hold':
                return bkp_client.cancel_legal_hold(**boto3_api_request_json)
            case 'list_recovery_points_by_backup_vault':
                return bkp_client.list_recovery_points_by_backup_vault(**boto3_api_request_json)
            case 'list_recovery_points_by_legal_hold':
                return bkp_client.list_recovery_points_by_legal_hold(**boto3_api_request_json)
            case 'list_recovery_points_by_resource':
                return bkp_client.list_recovery_points_by_resource(**boto3_api_request_json)
            case _:
                return {}
    except Exception as exception:
        raise exception


# Invoke boto3 APIs with LLM intervened retry
def invoke_boto3_api_with_llm_intervened_retry(aws_account_id, aws_region, bkp_client,
                                               boto3_api_name, boto3_api_request_json):
    try:
        try:
            response = invoke_boto3_api(bkp_client, boto3_api_name, boto3_api_request_json)
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
            response = invoke_boto3_api(bkp_client, boto3_api_name, fixed_boto3_api_request_json)
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
    aws_region, boto3_api_name, boto3_api_json_text = '', '', ''
    input_text = event["inputText"]
    # Loop through the input parameters
    input_parameters = event["parameters"]
    for input_parameter in input_parameters:
        # Retrieve the value of the parameters
        if input_parameter["name"] == "AWSRegion":
            aws_region = input_parameter["value"]
        elif input_parameter["name"] == "Boto3APIName":
            boto3_api_name = input_parameter["value"].lower()
            boto3_api_name = substring_after(boto3_api_name, 'backup.client.')
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
    # Instantiate the AWS Backup boto3 client for the specific region
    bkp_client = boto3.client('backup', region_name=aws_region, config=get_boto_config())
    # Except for custom APIs, validate the boto3 JSON for the specified user input by invoking a LLM
    if boto3_api_name not in ('list_backup_selections_using_backup_plan_name',
                              'list_backup_vaults_for_tags',
                              'list_backup_plans_for_tags',
                              'get_backup_vault_using_name',
                              'get_backup_vault_using_arn',
                              'get_backup_plan_using_name',
                              'get_backup_selection_using_name',
                              'delete_backup_vault_using_name',
                              'delete_backup_vault_using_arn',
                              'delete_backup_plan_using_name',
                              'delete_backup_selection_using_name',
                              'list_legal_holds_for_tags',
                              'get_legal_hold_using_arn',
                              'cancel_legal_hold_using_arn'):
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
        if boto3_api_name in ['create_backup_vault', 'create_logically_air_gapped_backup_vault']:
            # Parse the JSON
            create_backup_vault_json = json.loads(boto3_api_json_text)
            # Get the backup vault name
            backup_vault_name = create_backup_vault_json['BackupVaultName']
            # Check if the backup vault exists
            backup_vault_exists, retrieved_backup_vault_arn = does_backup_vault_exist_for_name(bkp_client, backup_vault_name)
            if backup_vault_exists:
                # Append to the response body text
                response_body_text = ('Backup vault with name "{}" and ARN "{}" already exists.'
                                      .format(backup_vault_name, retrieved_backup_vault_arn))
                response_body_text_list.append(response_body_text)
                logging.warning(response_body_text)
            else:
                # Create the backup vault by invoking the API
                try:
                    if boto3_api_name == 'create_backup_vault':
                        logging.info('Creating the backup vault...')
                        create_backup_vault_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                  aws_region,
                                                                                                  bkp_client,
                                                                                                  'create_backup_vault',
                                                                                                  create_backup_vault_json)
                        logging.info('Completed creating the backup vault.')
                    else:
                        logging.info('Creating the logically air gapped backup vault...')
                        create_backup_vault_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                  aws_region,
                                                                                                  bkp_client,
                                                                                                  'create_logically_air_gapped_backup_vault',
                                                                                                  create_backup_vault_json)
                        logging.info('Completed creating the logically air gapped backup vault.')
                    # Get the backup vault ARN
                    retrieved_backup_vault_arn = create_backup_vault_response['BackupVaultArn']
                    # Append to the response body text
                    if boto3_api_name == 'create_backup_vault':
                        response_body_text_list.append('Backup vault with name "{}" and ARN "{}" has been created.'
                                                       .format(backup_vault_name, retrieved_backup_vault_arn))
                    else:
                        response_body_text_list.append('Logically air gapped backup vault with name "{}" and ARN "{}" has been created.'
                                                       .format(backup_vault_name, retrieved_backup_vault_arn))
                except Exception as exception:
                    function_response_state = 'FAILURE'
                    # Append to the response body text
                    if boto3_api_name == 'create_backup_vault':
                        response_body_text = ('Error occurred while creating backup vault with name "{}" :: "{}"'
                                              .format(backup_vault_name, exception))
                    else:
                        response_body_text = ('Error occurred while creating logically air gapped backup vault with name "{}" :: "{}"'
                                              .format(backup_vault_name, exception))
                    response_body_text_list.append(response_body_text)
                    logging.error(response_body_text)
        elif boto3_api_name == 'create_backup_plan':
            # Parse the JSON
            create_backup_plan_json = json.loads(boto3_api_json_text)
            # Get the backup plan name
            backup_plan_name = create_backup_plan_json['BackupPlan']['BackupPlanName']
            # Check if the backup plan exists
            backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client, backup_plan_name)
            if backup_plan_exists:
                # Append to the response body text
                response_body_text = ('Backup plan with name "{}" and id "{}" already exists.'
                                      .format(backup_plan_name, retrieved_backup_plan_id))
                response_body_text_list.append(response_body_text)
                logging.warning(response_body_text)
            else:
                # Get the backup plan rules
                backup_plan_rules = create_backup_plan_json['BackupPlan']['Rules']
                # Loop through the backup plan rules
                for backup_plan_rule in backup_plan_rules:
                    # Get the backup vault name
                    retrieved_backup_vault_name = backup_plan_rule['TargetBackupVaultName']
                    # Check and create the backup vault
                    check_and_create_backup_vault(bkp_client, retrieved_backup_vault_name, response_body_text_list)
                # Create the backup plan by invoking the API
                try:
                    logging.info('Creating the backup plan...')
                    create_backup_plan_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                             aws_region,
                                                                                             bkp_client,
                                                                                             'create_backup_plan',
                                                                                             create_backup_plan_json)
                    logging.info('Completed creating the backup plan.')
                    # Get the backup plan id
                    retrieved_backup_plan_id = create_backup_plan_response['BackupPlanId']
                    # Append to the response body text
                    response_body_text_list.append('Backup plan with name "{}" and id "{}" has been created.'
                                                   .format(backup_plan_name, retrieved_backup_plan_id))
                except Exception as exception:
                    function_response_state = 'FAILURE'
                    # Append to the response body text
                    response_body_text = ('Error occurred while creating backup plan with name "{}" :: "{}"'
                                          .format(backup_plan_name, exception))
                    response_body_text_list.append(response_body_text)
                    logging.error(response_body_text)
        elif boto3_api_name == 'update_backup_plan':
            # Parse the JSON
            update_backup_plan_json = json.loads(boto3_api_json_text)
            # Get the backup plan name
            backup_plan_name = update_backup_plan_json['BackupPlan']['BackupPlanName']
            # Check if the backup plan exists
            backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client, backup_plan_name)
            if backup_plan_exists:
                # Get the backup plan rules
                backup_plan_rules = update_backup_plan_json['BackupPlan']['Rules']
                # Loop through the backup plan rules
                for backup_plan_rule in backup_plan_rules:
                    # Get the backup vault name
                    retrieved_backup_vault_name = backup_plan_rule['TargetBackupVaultName']
                    # Check and create the backup vault
                    check_and_create_backup_vault(bkp_client, retrieved_backup_vault_name, response_body_text_list)
                # Update the backup plan by invoking the API
                try:
                    logging.info('Updating the backup plan...')
                    update_backup_plan_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                             aws_region,
                                                                                             bkp_client,
                                                                                             'update_backup_plan',
                                                                                             update_backup_plan_json)
                    logging.info('Completed updating the backup plan.')
                    # Get the backup plan id
                    retrieved_backup_plan_id = update_backup_plan_response['BackupPlanId']
                    # Append to the response body text
                    response_body_text_list.append('Backup plan with name "{}" and id "{}" has been updated.'
                                                   .format(backup_plan_name, retrieved_backup_plan_id))
                except Exception as exception:
                    function_response_state = 'FAILURE'
                    # Append to the response body text
                    response_body_text = ('Error occurred while updating backup plan with name "{}" :: "{}"'
                                          .format(backup_plan_name, exception))
                    response_body_text_list.append(response_body_text)
                    logging.error(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup plan with name "{}" and id "{}" does not exist.'
                                      .format(backup_plan_name, retrieved_backup_plan_id))
                response_body_text_list.append(response_body_text)
                logging.warning(response_body_text)
        elif boto3_api_name == 'create_backup_selection':
            # Parse the JSON
            create_backup_selection_json = json.loads(boto3_api_json_text)
            # Check the backup plan id and process accordingly
            if 'BackupPlanId' in create_backup_selection_json:
                # Get the backup selection name and plan id
                backup_selection_name = create_backup_selection_json['BackupSelection']['SelectionName']
                retrieved_backup_plan_id = create_backup_selection_json['BackupPlanId']
                # Check if the backup selection exists
                backup_selection_exists, retreived_backup_selection_name_id = does_backup_selection_exist_for_name(bkp_client,
                                                                                                          retrieved_backup_plan_id,
                                                                                                          backup_selection_name)
                if backup_selection_exists:
                    # Append to the response body text
                    response_body_text = ('Backup selection with name "{}" and id "{}" already exists.'
                                          .format(backup_selection_name, retreived_backup_selection_name_id))
                    response_body_text_list.append(response_body_text)
                    logging.warning(response_body_text)
                else:
                    # Create the backup selection for the plan by invoking the API
                    try:
                        logging.info('Creating the backup selection...')
                        create_backup_selection_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                      aws_region,
                                                                                                      bkp_client,
                                                                                                      'create_backup_selection',
                                                                                                      create_backup_selection_json)
                        logging.info('Completed creating the backup selection.')
                        # Get the backup selection id
                        retrieved_backup_selection_id = create_backup_selection_response['SelectionId']
                        # Append to the response body text
                        response_body_text_list.append('Backup selection with name "{}" and id "{}" has been created for backup plan id "{}".'
                                                       .format(backup_selection_name, retrieved_backup_selection_id, retrieved_backup_plan_id))
                    except Exception as exception:
                        function_response_state = 'FAILURE'
                        # Append to the response body text
                        response_body_text = ('Error occurred while creating backup selection with name "{}" for backup plan id "{}" :: "{}"'
                                              .format(backup_selection_name, retrieved_backup_plan_id, exception))
                        response_body_text_list.append(response_body_text)
                        logging.error(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup plan id is missing. It is required to create the backup selection.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_backup_vaults':
            # Parse the JSON
            list_backup_vaults_json = json.loads(boto3_api_json_text)
            if list_backup_vaults_json is None:
                list_backup_vaults_json = {}
            # Specify the max results restriction
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Set the max records
            list_backup_vaults_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            # List the backup vaults by invoking the API
            logging.info('Listing backup vaults...')
            list_backup_vaults_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                     aws_region,
                                                                                     bkp_client,
                                                                                     'list_backup_vaults',
                                                                                     list_backup_vaults_json)
            logging.info('Completed listing backup vaults.')
            # Append to the response body text
            response_body_text_list.append('List of backup vaults :: "{}"'.format(list_backup_vaults_response['BackupVaultList']))
        elif boto3_api_name == 'list_backup_vaults_for_tags':
            # Parse the JSON
            list_backup_vaults_for_tags_json = json.loads(boto3_api_json_text)
            # Get the backup vault tags
            retrieved_tag_name = list_backup_vaults_for_tags_json['BackupVaultTagName']
            retrieved_tag_values = list_backup_vaults_for_tags_json['BackupVaultTagValues']
            if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                retrieved_tag_values = retrieved_tag_values.split(',')
                # Get the backup vaults that have the matching tags
                logging.info('Getting back vaults for tag "{}" with values {}...'.format(retrieved_tag_name,
                                                                                         retrieved_tag_values))
                list_backup_vaults_for_tags_response = list_backup_vaults_for_tags(bkp_client,
                                                                                   retrieved_tag_name,
                                                                                   retrieved_tag_values)
                logging.info('Getting back vaults for tag with values.')
                # Append to the response body text
                response_body_text_list.append(
                    'Results restricted to a max of {} item(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                response_body_text_list.append(
                    'Details of backup vaults associated with tag "{}" and with values {} :: {}'.format(retrieved_tag_name,
                                                                                                        retrieved_tag_values,
                                                                                                        list_backup_vaults_for_tags_response))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('One or more backup vault tag name and/or value is missing. '
                                      'It is required to get the backup vault details.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_protected_resources':
            # Parse the JSON
            list_protected_resources_json = json.loads(boto3_api_json_text)
            if list_protected_resources_json is None:
                list_protected_resources_json = {}
            # Set the max records
            list_protected_resources_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # List the protected resources by invoking the API
            logging.info('Listing protected resources...')
            list_protected_resources_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                           aws_region,
                                                                                           bkp_client,
                                                                                           'list_protected_resources',
                                                                                           list_protected_resources_json)
            logging.info('Completed listing protected resources.')
            # Append to the response body text
            response_body_text_list.append('List of protected resources :: "{}"'.format(list_protected_resources_response['Results']))
        elif boto3_api_name == 'list_protected_resources_by_backup_vault':
            # Parse the JSON
            list_protected_resources_by_backup_vault_json = json.loads(boto3_api_json_text)
            if list_protected_resources_by_backup_vault_json is None:
                list_protected_resources_by_backup_vault_json = {}
            # Set the max records
            list_protected_resources_by_backup_vault_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # Check the backup vault name and process accordingly
            if 'BackupVaultName' in list_protected_resources_by_backup_vault_json:
                retrieved_backup_vault_name = list_protected_resources_by_backup_vault_json['BackupVaultName']
                # List the protected resources by backup vault by invoking the API
                logging.info('Listing protected resources by backup vault...')
                list_protected_resources_by_backup_vault_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                               aws_region,
                                                                                               bkp_client,
                                                                                               'list_protected_resources_by_backup_vault',
                                                                                               list_protected_resources_by_backup_vault_json)
                logging.info('Completed listing protected resources by backup vault.')
                # Append to the response body text
                response_body_text_list.append('List of protected resources for backup vault named "{}" :: "{}"'.format(retrieved_backup_vault_name,
                                                                                                                        list_protected_resources_by_backup_vault_response['Results']))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup vault name is missing. '
                                      'It is required to get the backup vault.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_backup_jobs':
            # Parse the JSON
            list_backup_jobs_json = json.loads(boto3_api_json_text)
            if list_backup_jobs_json is None:
                list_backup_jobs_json = {}
            # Set the max records
            list_backup_jobs_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # List the backup jobs by invoking the API
            logging.info('Listing backup jobs...')
            list_backup_jobs_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                   aws_region,
                                                                                   bkp_client,
                                                                                   'list_backup_jobs',
                                                                                   list_backup_jobs_json)
            logging.info('Completed listing backup jobs.')
            # Append to the response body text
            response_body_text_list.append(
                'List of backup jobs :: "{}"'.format(list_backup_jobs_response['BackupJobs']))
        elif boto3_api_name == 'list_backup_plans':
            # Parse the JSON
            list_backup_plans_json = json.loads(boto3_api_json_text)
            if list_backup_plans_json is None:
                list_backup_plans_json = {}
            # Set the max records
            list_backup_plans_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # List the backup plans by invoking the API
            logging.info('Listing backup plans...')
            list_backup_plans_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                    aws_region,
                                                                                    bkp_client,
                                                                                    'list_backup_plans',
                                                                                    list_backup_plans_json)
            logging.info('Completed listing backup plans.')
            # Append to the response body text
            response_body_text_list.append('List of backup plans :: "{}"'.format(list_backup_plans_response['BackupPlansList']))
        elif boto3_api_name == 'list_backup_plans_for_tags':
            # Parse the JSON
            list_backup_plans_for_tags_json = json.loads(boto3_api_json_text)
            # Get the backup plan tags
            retrieved_tag_name = list_backup_plans_for_tags_json['BackupPlanTagName']
            retrieved_tag_values = list_backup_plans_for_tags_json['BackupPlanTagValues']
            if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                retrieved_tag_values = retrieved_tag_values.split(',')
                # Get the backup plans that have the matching tags
                logging.info('Getting backup plans for tag "{}" with values {}...'.format(retrieved_tag_name,
                                                                                         retrieved_tag_values))
                list_backup_plans_for_tags_response = list_backup_plans_for_tags(bkp_client,
                                                                                 retrieved_tag_name,
                                                                                 retrieved_tag_values)
                logging.info('Getting backup plans for tag with values.')
                # Append to the response body text
                response_body_text_list.append(
                    'Results restricted to a max of {} item(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                response_body_text_list.append(
                    'Details of backup plans associated with tag "{}" and with values {} :: {}'.format(retrieved_tag_name,
                                                                                                        retrieved_tag_values,
                                                                                                        list_backup_plans_for_tags_response))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('One or more backup plan tag name and/or value is missing. '
                                      'It is required to get the backup plan details.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['list_backup_selections', 'list_backup_selections_using_backup_plan_name']:
            # Parse the JSON
            list_backup_selections_json = json.loads(boto3_api_json_text)
            # Check if the user provided the name instead of the id of the backup plan
            if boto3_api_name == 'list_backup_selections_using_backup_plan_name':
                retrieved_backup_plan_name = list_backup_selections_json['BackupPlanName']
                backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client,
                                                                                               retrieved_backup_plan_name)
                logging.info('Retrieved "{}" as the id of the backup plan with name "{}".'.format(retrieved_backup_plan_id,
                                                                                                  retrieved_backup_plan_name))
                # Create the list backup selections boto3 API JSON
                list_backup_selections_json = json.loads('{"BackupPlanId": "' + retrieved_backup_plan_id + '"}')
            # Check the backup plan id and process accordingly
            if 'BackupPlanId' in list_backup_selections_json:
                # Set the max records
                list_backup_selections_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Get the backup plan id
                retrieved_backup_plan_id = list_backup_selections_json['BackupPlanId']
                # List the backup selections by invoking the API
                logging.info('Listing backup selections...')
                list_backup_selections_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                             aws_region,
                                                                                             bkp_client,
                                                                                             'list_backup_selections',
                                                                                             list_backup_selections_json)
                logging.info('Completed listing backup selections.')
                # Append to the response body text
                response_body_text_list.append(
                    'List of backup selections for backup id "{}" :: "{}"'
                    .format(retrieved_backup_plan_id, list_backup_selections_response['BackupSelectionsList']))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup plan id is missing. It is required to get the list of backup selections.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['get_backup_vault_using_name', 'get_backup_vault_using_arn']:
            # Parse the JSON
            get_backup_vault_json = json.loads(boto3_api_json_text)
            retrieved_backup_vault_name = get_backup_vault_json['BackupVaultName']
            retrieved_backup_vault_arn = get_backup_vault_json['BackupVaultArn']
            # Check the value that the user provided and process accordingly
            if len(retrieved_backup_vault_name) > 0:
                # Specify the max results restriction
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                logging.info('Getting backup vault details...')
                backup_vault_exists, retrieved_backup_vault_details = get_backup_vault_for_name(bkp_client,
                                                                                               retrieved_backup_vault_name)
                logging.info('Completed getting backup vault details.')
                if backup_vault_exists:
                    response_body_text_list.append('Details of backup vault with name "{}" :: {}'
                                                   .format(retrieved_backup_vault_name, retrieved_backup_vault_details))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('Backup vault with name "{}" does not exist.'
                                          .format(retrieved_backup_vault_name))
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif len(retrieved_backup_vault_arn) > 0:
                # Specify the max results restriction
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                logging.info('Getting backup vault details...')
                backup_vault_exists, retrieved_backup_vault_details = get_backup_vault_for_arn(bkp_client,
                                                                                              retrieved_backup_vault_arn)
                logging.info('Completed getting backup vault details.')
                if backup_vault_exists:
                    response_body_text_list.append('Details of backup vault with ARN "{}" :: {}'
                                                   .format(retrieved_backup_vault_arn, retrieved_backup_vault_details))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('Backup vault with ARN "{}" does not exist.'
                                          .format(retrieved_backup_vault_arn))
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup vault name or ARN is missing. '
                                      'It is required to get the backup vault.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['get_backup_plan', 'get_backup_plan_using_name']:
            # Parse the JSON
            get_backup_plan_json = json.loads(boto3_api_json_text)
            # Check if the user provided the name instead of the id of the backup plan
            if boto3_api_name == 'get_backup_plan_using_name':
                retrieved_backup_plan_name = get_backup_plan_json['BackupPlanName']
                backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client,
                                                                                               retrieved_backup_plan_name)
                logging.info('Retrieved "{}" as the id of the backup plan with name "{}".'.format(retrieved_backup_plan_id,
                                                                                                  retrieved_backup_plan_name))
                # Create the get backup plan boto3 API JSON
                get_backup_plan_json = json.loads('{"BackupPlanId": "' + retrieved_backup_plan_id + '"}')
            # Check the backup plan id and process accordingly
            if 'BackupPlanId' in get_backup_plan_json:
                # Get the backup plan id
                retrieved_backup_plan_id = get_backup_plan_json['BackupPlanId']
                # Get the backup plan details by invoking the API
                logging.info('Getting backup plan details...')
                get_backup_plan_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                      aws_region,
                                                                                      bkp_client,
                                                                                      'get_backup_plan',
                                                                                      get_backup_plan_json)
                logging.info('Completed getting backup plan details.')
                # Append to the response body text
                response_body_text_list.append('Details of backup plan with id "{}" :: {}'
                                               .format(retrieved_backup_plan_id, get_backup_plan_response))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup plan id is missing or could not determined from the backup plan name. '
                                      'It is required to get the backup plan.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['get_backup_selection', 'get_backup_selection_using_name']:
            # Parse the JSON
            get_backup_selection_json = json.loads(boto3_api_json_text)
            # Check if the user provided the name of the backup plan instead of the id and process accordingly
            if 'BackupPlanName' in get_backup_selection_json:
                retrieved_backup_plan_name = get_backup_selection_json['BackupPlanName']
                backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client,
                                                                                               retrieved_backup_plan_name)
                get_backup_selection_json['BackupPlanId'] = retrieved_backup_plan_id
            # Check if the user provided the name instead of the id of the backup selection
            if boto3_api_name == 'get_backup_selection_using_name':
                retrieved_backup_plan_id = get_backup_selection_json['BackupPlanId']
                retrieved_backup_selection_name = get_backup_selection_json['BackupSelectionName']
                backup_plan_exists, retrieved_backup_selection_id = does_backup_selection_exist_for_name(bkp_client,
                                                                                                         retrieved_backup_plan_id,
                                                                                                         retrieved_backup_selection_name)
                logging.info('Retrieved "{}" as the id of the backup selection with name "{}" associated with backup plan id "{}".'
                             .format(retrieved_backup_selection_id, retrieved_backup_selection_name, retrieved_backup_plan_id))
                # Create the get backup selection boto3 API JSON
                get_backup_selection_json = json.loads('{"BackupPlanId": "' + retrieved_backup_plan_id
                                                       + '", "SelectionId": "' + retrieved_backup_selection_id + '"}')
            # Check the backup plan id and selection id and process accordingly
            if 'BackupPlanId' not in get_backup_selection_json:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup plan id is missing. It is required to get the backup selection.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
            elif 'SelectionId' not in get_backup_selection_json:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup selection id is missing. It is required to get the backup selection.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
            else:
                # Get the backup plan id and selection id
                retrieved_backup_plan_id = get_backup_selection_json['BackupPlanId']
                retrieved_backup_selection_id = get_backup_selection_json['SelectionId']
                # Check if the backup plan exists
                backup_plan_exists, retrieved_backup_plan_name = does_backup_plan_exist_for_id(bkp_client,
                                                                                               retrieved_backup_plan_id)
                # Process accordingly
                if backup_plan_exists:
                    # Check if the backup selection exists
                    backup_selection_exists, retrieved_backup_selection_name \
                        = does_backup_selection_exist_for_id(bkp_client,
                                                             retrieved_backup_plan_id,
                                                             retrieved_backup_selection_id)
                    # Process accordingly
                    if backup_selection_exists:
                        logging.info('Getting backup selection details...')
                        get_backup_selection_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                   aws_region,
                                                                                                   bkp_client,
                                                                                                   'get_backup_selection',
                                                                                                   get_backup_selection_json)
                        logging.info('Completed getting backup selection details.')
                        # Append to the response body text
                        response_body_text_list.append('Details of backup selection with id "{}" in backup plan with id "{}" :: {}'
                                                       .format(retrieved_backup_selection_id,
                                                               retrieved_backup_plan_id,
                                                               get_backup_selection_response))
                    else:
                        # Append to the response body text
                        response_body_text = ('Backup selection with id "{}" in backup plan with id "{}" does not exist.'
                                              .format(retrieved_backup_selection_id, retrieved_backup_plan_id))
                        response_body_text_list.append(response_body_text)
                        logging.warning(response_body_text)
                else:
                    # Append to the response body text
                    response_body_text = ('Backup plan with id "{}" does not exist.'
                                          .format(retrieved_backup_plan_id))
                    response_body_text_list.append(response_body_text)
                    logging.warning(response_body_text)
        elif boto3_api_name in ['delete_backup_vault_using_name', 'delete_backup_vault_using_arn']:
            # Parse the JSON
            delete_backup_vault_json = json.loads(boto3_api_json_text)
            retrieved_backup_vault_name = delete_backup_vault_json['BackupVaultName']
            retrieved_backup_vault_arn = delete_backup_vault_json['BackupVaultArn']
            # Check the value that the user provided and process accordingly
            if len(retrieved_backup_vault_name) > 0:
                logging.info('Getting backup vault details...')
                backup_vault_exists, retrieved_backup_vault_details = get_backup_vault_for_name(bkp_client,
                                                                                               retrieved_backup_vault_name)
                logging.info('Completed getting backup vault details.')
                if backup_vault_exists:
                    # Check if the backup vault is empty and delete accordingly
                    if retrieved_backup_vault_details['NumberOfRecoveryPoints'] > 0:
                        response_body_text_list.append('Cannot delete backup vault with name "{}" :: it is not empty.'
                                                       .format(retrieved_backup_vault_name))
                    else:
                        logging.info('Deleting backup vault...')
                        bkp_client.delete_backup_vault(BackupVaultName=retrieved_backup_vault_name)
                        logging.info('Completed deleting backup vault.')
                        response_body_text_list.append('Backup vault with name "{}" has been deleted.'
                                                       .format(retrieved_backup_vault_name))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('Backup vault with name "{}" does not exist.'
                                          .format(retrieved_backup_vault_name))
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            elif len(retrieved_backup_vault_arn) > 0:
                logging.info('Getting backup vault details...')
                backup_vault_exists, retrieved_backup_vault_details = get_backup_vault_for_arn(bkp_client,
                                                                                              retrieved_backup_vault_arn)
                logging.info('Completed getting backup vault details.')
                if backup_vault_exists:
                    # Check if the backup vault is empty and delete accordingly
                    if retrieved_backup_vault_details['NumberOfRecoveryPoints'] > 0:
                        response_body_text_list.append('Cannot delete backup vault with ARN "{}" :: it is not empty.'
                                                       .format(retrieved_backup_vault_arn))
                    else:
                        logging.info('Deleting backup vault...')
                        bkp_client.delete_backup_vault(BackupVaultName=retrieved_backup_vault_details['BackupVaultName'])
                        logging.info('Completed deleting backup vault.')
                        response_body_text_list.append('Backup vault with ARN "{}" has been deleted.'
                                                       .format(retrieved_backup_vault_arn))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = ('Backup vault with ARN "{}" does not exist.'
                                          .format(retrieved_backup_vault_arn))
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup vault name or ARN is missing. '
                                      'It is required to delete the backup vault.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['delete_backup_plan', 'delete_backup_plan_using_name']:
            # Parse the JSON
            delete_backup_plan_json = json.loads(boto3_api_json_text)
            # Check if the user provided the name instead of the id of the backup plan
            if boto3_api_name == 'delete_backup_plan_using_name':
                retrieved_backup_plan_name = delete_backup_plan_json['BackupPlanName']
                backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client,
                                                                                               retrieved_backup_plan_name)
                logging.info('Retrieved "{}" as the id of the backup plan with name "{}".'.format(retrieved_backup_plan_id,
                                                                                                  retrieved_backup_plan_name))
                # Create the delete backup plan boto3 API JSON
                delete_backup_plan_json = json.loads('{"BackupPlanId": "' + retrieved_backup_plan_id + '"}')
            # Check the backup plan id and process accordingly
            if 'BackupPlanId' in delete_backup_plan_json:
                # Get the backup plan id
                retrieved_backup_plan_id = delete_backup_plan_json['BackupPlanId']
                # Check if the backup plan exists
                backup_plan_exists, retrieved_backup_plan_name = does_backup_plan_exist_for_id(bkp_client,
                                                                                               retrieved_backup_plan_id)
                # Process accordingly
                if backup_plan_exists:
                    # Get the list of all the backup selections for this backup plan
                    backup_selections = (bkp_client.list_backup_selections(BackupPlanId=retrieved_backup_plan_id))[
                        'BackupSelectionsList']
                    # Loop the backup selections
                    for backup_selection in backup_selections:
                        # Delete the backup selection
                        retrieved_backup_selection_id = backup_selection['SelectionId']
                        logging.info('Deleting backup selection with id "{}"...'.format(retrieved_backup_selection_id))
                        bkp_client.delete_backup_selection(BackupPlanId=retrieved_backup_plan_id,
                                                           SelectionId=retrieved_backup_selection_id)
                        logging.info('Completed deleting backup selection.')
                        # Append to the response body text
                        response_body_text_list.append(
                            'Backup selection with id "{}" in backup plan with name "{}" has been deleted.'
                            .format(retrieved_backup_selection_id, retrieved_backup_plan_name))
                    # Delete the specified backup plan by invoking the API
                    logging.info('Deleting backup plan...')
                    delete_backup_plan_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                             aws_region,
                                                                                             bkp_client,
                                                                                             'delete_backup_plan',
                                                                                             delete_backup_plan_json)
                    logging.info('Completed deleting backup plan.')
                    # Append to the response body text
                    response_body_text_list.append('Backup plan with name "{}" and id "{}" has been deleted on "{}".'
                                                   .format(retrieved_backup_plan_name,
                                                           retrieved_backup_plan_id,
                                                           delete_backup_plan_response['DeletionDate']))
                else:
                    # Append to the response body text
                    response_body_text = ('Backup plan with id "{}" does not exist.'
                                          .format(retrieved_backup_plan_id))
                    response_body_text_list.append(response_body_text)
                    logging.warning(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Backup plan id is missing or could not determined from the backup plan name. '
                                      'It is required to delete the backup plan.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['delete_backup_selection', 'delete_backup_selection_using_name']:
            # Parse the JSON
            delete_backup_selection_json = json.loads(boto3_api_json_text)
            # Check if the user provided the name of the backup plan instead of the id and process accordingly
            if 'BackupPlanName' in delete_backup_selection_json:
                retrieved_backup_plan_name = delete_backup_selection_json['BackupPlanName']
                backup_plan_exists, retrieved_backup_plan_id = does_backup_plan_exist_for_name(bkp_client,
                                                                                               retrieved_backup_plan_name)
                delete_backup_selection_json['BackupPlanId'] = retrieved_backup_plan_id
            # Check if the user provided the name instead of the id of the backup selection
            if boto3_api_name == 'delete_backup_selection_using_name':
                retrieved_backup_plan_id = delete_backup_selection_json['BackupPlanId']
                retrieved_backup_selection_name = delete_backup_selection_json['BackupSelectionName']
                backup_selection_exists, retrieved_backup_selection_id = does_backup_selection_exist_for_name(bkp_client,
                                                                                                              retrieved_backup_plan_id,
                                                                                                              retrieved_backup_selection_name)
                logging.info('Retrieved "{}" as the id of the backup selection with name "{}" associated with backup plan id "{}".'
                             .format(retrieved_backup_selection_id, retrieved_backup_selection_name, retrieved_backup_plan_id))
                # Create the delete backup selection boto3 API JSON
                delete_backup_selection_json = json.loads('{"BackupPlanId": "' + retrieved_backup_plan_id
                                                          + '", "SelectionId": "' + retrieved_backup_selection_id + '"}')
            # Check the backup plan id and selection id and process accordingly
            if 'BackupPlanId' not in delete_backup_selection_json:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup plan id is missing or could not determined from the backup plan name. It is required to delete the backup selection.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
            elif 'SelectionId' not in delete_backup_selection_json:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup selection id is missing. It is required to delete the backup selection.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
            else:
                # Get the backup plan id and selection id
                retrieved_backup_plan_id = delete_backup_selection_json['BackupPlanId']
                retrieved_backup_selection_id = delete_backup_selection_json['SelectionId']
                # Check if the backup plan exists
                backup_plan_exists, retrieved_backup_plan_name = does_backup_plan_exist_for_id(bkp_client,
                                                                                               retrieved_backup_plan_id)
                # Process accordingly
                if backup_plan_exists:
                    # Check if the backup selection exists
                    backup_selection_exists, retrieved_backup_selection_name \
                        = does_backup_selection_exist_for_id(bkp_client,
                                                             retrieved_backup_plan_id,
                                                             retrieved_backup_selection_id)
                    # Process accordingly
                    if backup_selection_exists:
                        logging.info('Deleting backup selection...')
                        invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                   aws_region,
                                                                   bkp_client,
                                                                   'delete_backup_selection',
                                                                   delete_backup_selection_json)
                        logging.info('Completed deleting backup selection.')
                        # Append to the response body text
                        response_body_text_list.append(
                            'Backup selection with id "{}" in backup plan with id "{}" has been deleted.'
                            .format(retrieved_backup_selection_id, retrieved_backup_plan_id))
                    else:
                        # Append to the response body text
                        response_body_text = ('Backup selection with id "{}" in backup plan with id "{}" does not exist.'
                                              .format(retrieved_backup_selection_id, retrieved_backup_plan_id))
                        response_body_text_list.append(response_body_text)
                        logging.warning(response_body_text)
                else:
                    # Append to the response body text
                    response_body_text = ('Backup plan with id "{}" does not exist.'
                                          .format(retrieved_backup_plan_id))
                    response_body_text_list.append(response_body_text)
                    logging.warning(response_body_text)
        elif boto3_api_name == 'create_legal_hold':
            # Parse the JSON
            create_legal_hold_json = json.loads(boto3_api_json_text)
            # Create the legal hold by invoking the API
            try:
                logging.info('Creating the legal hold...')
                create_legal_hold_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                        aws_region,
                                                                                        bkp_client,
                                                                                        'create_legal_hold',
                                                                                        create_legal_hold_json)
                logging.info('Completed creating the legal hold.')
                # Get the legal hold id
                retrieved_legal_hold_id = create_legal_hold_response['LegalHoldId']
                # Append to the response body text
                response_body_text_list.append('Legal hold with id "{}" has been created.'
                                               .format(retrieved_legal_hold_id))
            except Exception as exception:
                function_response_state = 'FAILURE'
                # Append to the response body text
                response_body_text = ('Error occurred while creating legal hold :: "{}"'
                                      .format(exception))
                response_body_text_list.append(response_body_text)
                logging.error(response_body_text)
        elif boto3_api_name == 'list_legal_holds':
            # Parse the JSON
            list_legal_holds_json = json.loads(boto3_api_json_text)
            if list_legal_holds_json is None:
                list_legal_holds_json = {}
            # Set the max records
            list_legal_holds_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
            response_body_text_list.append(
                'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
            # List the legal holds by invoking the API
            logging.info('Listing legal holds...')
            list_legal_holds_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                   aws_region,
                                                                                   bkp_client,
                                                                                   'list_legal_holds',
                                                                                   list_legal_holds_json)
            logging.info('Completed listing legal holds.')
            # Append to the response body text
            response_body_text_list.append('List of legal holds :: "{}"'.format(list_legal_holds_response['LegalHolds']))
        elif boto3_api_name == 'list_legal_holds_for_tags':
            # Parse the JSON
            list_legal_holds_for_tags_json = json.loads(boto3_api_json_text)
            # Get the legal hold tags
            retrieved_tag_name = list_legal_holds_for_tags_json['LegalHoldTagName']
            retrieved_tag_values = list_legal_holds_for_tags_json['LegalHoldTagValues']
            if (len(retrieved_tag_name) > 0) and (len(retrieved_tag_values) > 0):
                retrieved_tag_values = retrieved_tag_values.split(',')
                # Get the legal holds that have the matching tags
                logging.info('Getting legal holds for tag "{}" with values {}...'.format(retrieved_tag_name,
                                                                                         retrieved_tag_values))
                list_legal_holds_for_tags_response = list_legal_holds_for_tags(bkp_client,
                                                                               retrieved_tag_name,
                                                                               retrieved_tag_values)
                logging.info('Getting legal holds for tag with values.')
                # Append to the response body text
                response_body_text_list.append(
                    'Results restricted to a max of {} item(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                response_body_text_list.append(
                    'Details of legal holds associated with tag "{}" and with values {} :: {}'.format(retrieved_tag_name,
                                                                                                        retrieved_tag_values,
                                                                                                        list_legal_holds_for_tags_response))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('One or more legal hold tag name and/or value is missing. '
                                      'It is required to get the legal hold details.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['get_legal_hold', 'get_legal_hold_using_arn']:
            # Parse the JSON
            get_legal_hold_json = json.loads(boto3_api_json_text)
            # Check if the user provided the ARN instead of the id of the legal hold
            if boto3_api_name == 'get_legal_hold_using_arn':
                retrieved_legal_hold_arn = get_legal_hold_json['LegalHoldArn']
                legal_hold_exists, retrieved_legal_hold_id = does_legal_hold_exist_for_arn(bkp_client,
                                                                                           retrieved_legal_hold_arn)
                logging.info('Retrieved "{}" as the id of the legal hold with ARN "{}".'.format(retrieved_legal_hold_id,
                                                                                                  retrieved_legal_hold_arn))
                # Create the get legal hold boto3 API JSON
                get_legal_hold_json = json.loads('{"LegalHoldId": "' + retrieved_legal_hold_id + '"}')
            # Check the legal hold id and process accordingly
            if 'LegalHoldId' in get_legal_hold_json:
                # Get the legal hold id
                retrieved_legal_hold_id = get_legal_hold_json['LegalHoldId']
                # Get the legal hold details by invoking the API
                logging.info('Getting legal hold details...')
                get_legal_hold_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                      aws_region,
                                                                                      bkp_client,
                                                                                      'get_legal_hold',
                                                                                      get_legal_hold_json)
                logging.info('Completed getting legal hold details.')
                # Append to the response body text
                response_body_text_list.append('Details of legal hold with id "{}" :: {}'
                                               .format(retrieved_legal_hold_id, get_legal_hold_response))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Legal hold id is missing or could not determined from the legal hold ARN. '
                                      'It is required to get the legal hold.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name in ['cancel_legal_hold', 'cancel_legal_hold_using_arn']:
            # Parse the JSON
            cancel_legal_hold_json = json.loads(boto3_api_json_text)
            # Check if the user provided the ARN instead of the id of the legal hold
            if boto3_api_name == 'cancel_legal_hold_using_arn':
                retrieved_legal_hold_arn = cancel_legal_hold_json['LegalHoldArn']
                legal_hold_exists, retrieved_legal_hold_id = does_legal_hold_exist_for_arn(bkp_client,
                                                                                           retrieved_legal_hold_arn)
                logging.info('Retrieved "{}" as the id of the legal hold with ARN "{}".'.format(retrieved_legal_hold_id,
                                                                                                  retrieved_legal_hold_arn))
                # Create the cancel legal hold boto3 API JSON
                cancel_legal_hold_json = json.loads('{"LegalHoldId": "' + retrieved_legal_hold_id + '"}')
            # Check the legal hold id and process accordingly
            if 'LegalHoldId' in cancel_legal_hold_json:
                # Get the legal hold id
                retrieved_legal_hold_id = cancel_legal_hold_json['LegalHoldId']
                # Get the legal hold details by invoking the API
                logging.info('Canceling legal hold...')
                invoke_boto3_api_with_llm_intervened_retry(aws_account_id, aws_region, bkp_client,
                                                           'cancel_legal_hold', cancel_legal_hold_json)
                logging.info('Completed canceling legal hold.')
                # Append to the response body text
                response_body_text_list.append('Canceled legal hold with id "{}".'.format(retrieved_legal_hold_id))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = ('Legal hold id is missing or could not determined from the legal hold ARN. '
                                      'It is required to cancel the legal hold.')
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_recovery_points_by_backup_vault':
            # Parse the JSON
            list_recovery_points_by_backup_vault_json = json.loads(boto3_api_json_text)
            # Check the backup vault name and process accordingly
            if 'BackupVaultName' in list_recovery_points_by_backup_vault_json:
                # Set the max records
                list_recovery_points_by_backup_vault_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Get the backup vault name
                retrieved_backup_vault_name = list_recovery_points_by_backup_vault_json['BackupVaultName']
                # Check if the backup vault exists
                backup_vault_exists, retrieved_backup_vault_arn = does_backup_vault_exist_for_name(bkp_client,
                                                                                                   retrieved_backup_vault_name)
                if backup_vault_exists:
                    # List the backup selections by invoking the API
                    logging.info('Listing recovery points by backup vault...')
                    list_recovery_points_by_backup_vault_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                               aws_region,
                                                                                                               bkp_client,
                                                                                                               'list_recovery_points_by_backup_vault',
                                                                                                               list_recovery_points_by_backup_vault_json)
                    logging.info('Completed listing recovery points by backup vault.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'List of recovery points for backup vault "{}" :: "{}"'
                        .format(retrieved_backup_vault_name, list_recovery_points_by_backup_vault_response['RecoveryPoints']))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'Backup vault with name "{}" does not exist.'.format(retrieved_backup_vault_name)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Backup vault name is missing. It is required to get the list of recovery points by vault.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_recovery_points_by_legal_hold':
            # Parse the JSON
            list_recovery_points_by_legal_hold_json = json.loads(boto3_api_json_text)
            # Check the legal hold id and process accordingly
            if 'LegalHoldId' in list_recovery_points_by_legal_hold_json:
                # Set the max records
                list_recovery_points_by_legal_hold_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Get the legal hold id
                retrieved_legal_hold_id = list_recovery_points_by_legal_hold_json['LegalHoldId']
                # Check if the legal hold exists
                legal_hold_exists, retrieved_legal_hold_arn = does_legal_hold_exist_for_id(bkp_client,
                                                                                           retrieved_legal_hold_id)
                if legal_hold_exists:
                    # List the recovery points by legal hold by invoking the API
                    logging.info('Listing recovery points by legal hold...')
                    list_recovery_points_by_legal_hold_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                               aws_region,
                                                                                                               bkp_client,
                                                                                                               'list_recovery_points_by_legal_hold',
                                                                                                               list_recovery_points_by_legal_hold_json)
                    logging.info('Completed listing recovery points by legal hold.')
                    # Append to the response body text
                    response_body_text_list.append(
                        'List of recovery points for legal hold id "{}" :: "{}"'
                        .format(retrieved_legal_hold_id, list_recovery_points_by_legal_hold_response['RecoveryPoints']))
                else:
                    function_response_state = 'REPROMPT'
                    # Append to the response body text
                    response_body_text = 'Legal hold with id "{}" does not exist.'.format(retrieved_legal_hold_id)
                    logging.warning(response_body_text)
                    response_body_text_list.append(response_body_text)
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Legal hold id is missing. It is required to get the list of recovery points by legal hold.'
                logging.warning(response_body_text)
                response_body_text_list.append(response_body_text)
        elif boto3_api_name == 'list_recovery_points_by_resource':
            # Parse the JSON
            list_recovery_points_by_resource_json = json.loads(boto3_api_json_text)
            # Check the resource ARN and process accordingly
            if 'ResourceArn' in list_recovery_points_by_resource_json:
                # Set the max records
                list_recovery_points_by_resource_json['MaxResults'] = int(os.environ['BOTO3_API_MAX_RESULTS'])
                response_body_text_list.append(
                    'Results restricted to a max of {} items(s). '.format(os.environ['BOTO3_API_MAX_RESULTS']))
                # Get the resource ARN
                retrieved_resource_arn = list_recovery_points_by_resource_json['ResourceArn']
                # List the recovery points by resource by invoking the API
                logging.info('Listing recovery points by resource...')
                list_recovery_points_by_resource_response = invoke_boto3_api_with_llm_intervened_retry(aws_account_id,
                                                                                                       aws_region,
                                                                                                       bkp_client,
                                                                                                       'list_recovery_points_by_resource',
                                                                                                       list_recovery_points_by_resource_json)
                logging.info('Completed listing recovery points by resource.')
                # Append to the response body text
                response_body_text_list.append(
                    'List of recovery points for resource ARN "{}" :: "{}"'
                    .format(retrieved_resource_arn, list_recovery_points_by_resource_response['RecoveryPoints']))
            else:
                function_response_state = 'REPROMPT'
                # Append to the response body text
                response_body_text = 'Resource ARN is missing. It is required to get the list of recovery points by resource.'
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