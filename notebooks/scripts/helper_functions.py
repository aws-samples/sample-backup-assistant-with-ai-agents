"""
Copyright 2025 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
import boto3
from botocore.exceptions import ClientError
import datetime
import json
import logging
import os
import requests
import sagemaker
import time
import uuid
from timeit import default_timer as timer

# Create the logger
DEFAULT_LOG_LEVEL = logging.NOTSET
DEFAULT_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
log_level = os.environ.get('LOG_LEVEL')
match log_level:
    case '10':
        log_level = logging.DEBUG
    case '20':
        log_level = logging.INFO
    case '30':
        log_level = logging.WARNING
    case '40':
        log_level = logging.ERROR
    case '50':
        log_level = logging.CRITICAL
    case _:
        log_level = DEFAULT_LOG_LEVEL
log_format = os.environ.get('LOG_FORMAT')
if log_format is None:
    log_format = DEFAULT_LOG_FORMAT
elif len(log_format) == 0:
    log_format = DEFAULT_LOG_FORMAT
# Set the basic config for the logger
logging.basicConfig(level=log_level, format=log_format)


def substring_after(source_string, substring) -> str:
    """
    Function to get the substring after a specified string within a source string.

    Parameters:
    source_string (str): The source string
    substring (str): The substring

    Returns:
    str: The string after the substring
    """
    source_string_parts = source_string.rsplit(substring, 1)
    return source_string_parts[1]


def download_file(download_url, dir_name) -> str:
    """
    Function to download the specified file to the specified directory

    Parameters:
    download_url (str): The URL of the file to download
    dir_name (str): The name of the directory where the file should be downloaded

    Returns:
    str: The name of the downloaded file
    """
    # Download the file
    response_content = requests.get(download_url, timeout=60).content
    # Write to local directory
    file_name = download_url.split("/")[-1]
    with open('{}/{}'.format(dir_name, file_name), "wb") as f:
        f.write(response_content)
        logging.info("Downloaded file '{}' to '{}'.".format(file_name, dir_name))
    return file_name


def delete_local_file(file_full_path) -> None:
    """
    Function to delete the specified file from a local directory.

    Parameters:
    file_full_path (str): The full path to the local file

    Returns:
    None
    """
    # Delete the file
    logging.info('Deleting local file "{}"...'.format(file_full_path))
    os.remove(file_full_path)
    logging.info('Completed deleting local file.')


def get_file_name_and_extension(file_full_path) -> tuple[str, str]:
    """
    Function to get the name and extension from the specified file path.

    Parameters:
    file_full_path (str): The file path

    Returns:
    tuple[str, str]: The file name and extension
    """
    file_name = ''
    file_extension = ''
    file_path_components = file_full_path.split('/')
    file_name_and_extension = file_path_components[-1].rsplit('.', 1)
    if len(file_name_and_extension) > 0:
        file_name = file_name_and_extension[0]
        if len(file_name_and_extension) > 1:
            file_extension = file_name_and_extension[1]
    return file_name, file_extension


def get_s3_bucket_name_from_arn(s3_arn):
    """
    Function to prepare the prompt

    Parameters:
    s3_arn (string): The ARN of the S3 bucket

    Returns:
    string: The S3 bucket name
    """
    return (s3_arn.split('arn:aws:s3:::', 1))[1]


def is_supported_file_type(data_file_full_path) -> bool:
    """
    Function to check if the specified data file is a supported type by Converse API or not.

    Parameters:
    data_file_full_path (str): The full path to the data file

    Returns:
    bool: The flag that indicates if this is a supported type or not
    """
    supported_file_types = ['pdf', 'csv', 'doc', 'docx', 'xls', 'xlsx', 'html', 'txt', 'md',
                            'png', 'jpeg', 'gif', 'webp']
    data_file_name, data_file_extension = get_file_name_and_extension(data_file_full_path)
    if data_file_extension in supported_file_types:
        logging.debug("The specified file '{}' of type '{}' is supported by Converse API.".format(data_file_full_path,
                                                                                                  data_file_extension))
        return True
    else:
        logging.warning("The specified file '{}' of type '{}' is not supported by Converse API.".format(data_file_full_path,
                                                                                                        data_file_extension))
        logging.info("Converse API supported file types are {}".format(supported_file_types))
        return False


def read_file(file_full_path, file_read_type) -> str | bytes:
    """
    Function to get the read the content of the specified file.

    Parameters:
    file_full_path (str): The path to the file
    file_read_type (str): File read type - r or rb

    Returns:
    string | bytes: The file content as string or bytes
    """
    with open(file_full_path, file_read_type) as file:
        file_content = file.read()
    return file_content


def upload_to_s3(dir_name, s3_bucket_name, s3_key_prefix):
    """
    Function to upload the specified file to the specified S3 location

    Parameters:
    dir_name (string): The name of the directory from where the file should be uploaded
    s3_bucket_name (string): The S3 bucket name
    s3_key_prefix (string): The name of the file which will also serve as the S3 key prefix

    Returns:
    None
    """
    # Upload to S3
    data_s3_path = sagemaker.Session().upload_data(path='{}/'.format(dir_name),
                                                   bucket=s3_bucket_name,
                                                   key_prefix=s3_key_prefix)
    logging.info("Uploaded file(s) from '{}' to '{}'.".format(dir_name, data_s3_path))


def does_br_agent_meet_requirements(bedrock_agt_client, br_agent_name) -> tuple[bool, str, str]:
    """
    Function to check if the specified Bedrock agent meets all requirements

    Parameters:
    bedrock_agt_client (AgentsforBedrock.Client): The boto3 client for Bedrock Agent
    br_agent_name (str): The name of the Bedrock Agent

    Returns:
    bool: The flag indicating if the specified Bedrock Agent meets requirements
    str: The id of the Bedrock Agent
    str: The version of the Bedrock Agent
    """
    # Initialize
    br_agent_id = ''
    br_agent_version = ''
    br_region = bedrock_agt_client.meta.region_name
    # Check if the agent name has been specified already
    if len(br_agent_name) > 0:
        # Get the list of agents
        list_agents_response = bedrock_agt_client.list_agents(
            maxResults=100
        )
        # Loop through the agent list
        agent_summaries = list_agents_response['agentSummaries']
        for agent_summary in agent_summaries:
            # Check the agent's prepared status
            if agent_summary['agentStatus'] == 'PREPARED':
                # Check the agent's name
                if br_agent_name == agent_summary['agentName']:
                    br_agent_id = agent_summary['agentId']
                    br_agent_version = agent_summary['latestAgentVersion']
                    break
        # Check if the agent id and version exists
        if (len(br_agent_id) > 0) and (len(br_agent_version) > 0):
            meets_requirements = True
            logging.info(
                "The specified Amazon Bedrock Agent '{}' meets all requirements. It's id is '{}' and it's version is '{}'.".
                format(br_agent_name, br_agent_id, br_agent_version))
            logging.info(
                "For more info on this Amazon Bedrock Agent, visit https://{}.console.aws.amazon.com/bedrock/home?region={}#/agents/{}"
                .format(br_region, br_region, br_agent_id))

        else:
            meets_requirements = False
            # If the specified agent is not active or not found, then print info for the user to create an agent
            logging.error("The specified Amazon Bedrock Agent '{}' was not found or not prepared or no alias was found.".format(br_agent_name))
            logging.info(
                "Refer to the requirements specified earlier and use the process described at {} to create an Amazon Bedrock agent in the same AWS Region as Amazon Bedrock and rerun this cell."
                .format("https://docs.aws.amazon.com/bedrock/latest/userguide/agents-create.html"))
    else:
        meets_requirements = False
        logging.error("No Amazon Bedrock Agent was specified.")
    return meets_requirements, br_agent_id, br_agent_version


def get_br_agent_alias_that_meets_requirements(bedrock_agt_client, br_agent_id, br_agent_alias_id) -> str:
    """
    Function to get the first available Bedrock agent alias that meets the requirements

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_agent_id (str): The id of the Bedrock Agent
    br_agent_alias_id (str): The id of the Bedrock Agent Alias

    Returns:
    str: The id of the Bedrock Agent Alias
    """
    # Initialize
    br_region = bedrock_agt_client.meta.region_name
    # Check if an agent alias id has been specified already
    if len(br_agent_alias_id) == 0:
        # If an agent alias has not been specified, then, attempt to retrieve the first available active agent alias
        logging.info(
            "No Amazon Bedrock Agent aliases specified for use. Will attempt to retrieve the first available agent alias that meets all requirements.")
        # Get the list of agent aliases associated with this agent
        list_agent_aliases_response = bedrock_agt_client.list_agent_aliases(
            agentId=br_agent_id,
            maxResults=100
        )
        # Loop through the agent alias list
        agent_alias_summaries = list_agent_aliases_response['agentAliasSummaries']
        for agent_alias_summary in agent_alias_summaries:
            br_agent_alias_id = agent_alias_summary['agentAliasId']
            # Check the prepared status and get the agent alias id; ignore the draft alias with id 'TSTALIASID'
            if (br_agent_alias_id != 'TSTALIASID') and (agent_alias_summary['agentAliasStatus'] == 'PREPARED'):
                br_agent_alias_name = agent_alias_summary['agentAliasName']
                logging.info("Found an Amazon Bedrock Agent alias that meets all requirements. It's id is '{}' and it's name is '{}'.".
                             format(br_agent_alias_id, br_agent_alias_name))
                logging.info(
                    "For more info on this Amazon Bedrock Agent alias, visit https://{}.console.aws.amazon.com/bedrock/home?region={}#/agents/{}/alias/{}"
                    .format(br_region, br_region, br_agent_id, br_agent_alias_id))
                break
        # Check if the agent alias id exists
        if len(br_agent_id) == 0:
            # If an active agent alias is still not found, then print info for the user to create an agent alias
            logging.error("No Amazon Bedrock Agent alias that meets all requirements was found.")
            logging.info(
                "Refer to the requirements specified earlier and use the process described at {} to create an Amazon Bedrock Agent alias in the same AWS Region as Amazon Bedrock and rerun this cell."
                .format("https://docs.aws.amazon.com/bedrock/latest/userguide/agents-alias-manage.html"))
    else:
        # If an agent alias has been specified, then, check if it meets all requirements
        get_agent_alias_response = bedrock_agt_client.get_agent_alias(
            agentAliasId=br_agent_alias_id,
            agentId=br_agent_id
        )
        if get_agent_alias_response['agentAlias']['agentAliasStatus'] == 'PREPARED':
            br_agent_alias_name = get_agent_alias_response['agentAlias']['agentAliasName']
            logging.info("The specified Amazon Bedrock Agent alias with id '{}' meets all requirements. This agent alias will be used. It's name is '{}'."
                         .format(br_agent_alias_id, br_agent_alias_name))
            logging.info(
                "For more info on this Amazon Bedrock Agent alias, visit https://{}.console.aws.amazon.com/bedrock/home?region={}#/agents/{}/alias/{}"
                .format(br_region, br_region, br_agent_id, br_agent_alias_id))
        else:
            logging.error("No Amazon Bedrock Agent aliases that meets all requirements was found.")
            logging.info(
                "Refer to the requirements specified earlier and use the process described at {} to create an Amazon Bedrock Agent alias in the same AWS Region as Amazon Bedrock and rerun this cell."
                .format("https://docs.aws.amazon.com/bedrock/latest/userguide/agents-alias-manage.html"))
    return br_agent_alias_id


def append_agent_kbs_to_list(kbs, bedrock_agt_client, br_agent_id, br_agent_version) -> None:
    """
    Function to retrieve the list of KBs associated with the specified agent and append to the specified list

    Parameters:
    kbs (list[str]): The list of KBs
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_agent_id (str): The id of the Bedrock Agent
    br_agent_version (str): The version of the Bedrock Agent

    Returns:
    None
    """
    # Get the KBs, if any, associated with the agent
    list_agent_kbs_response = bedrock_agt_client.list_agent_knowledge_bases(agentId=br_agent_id,
                                                                            agentVersion=br_agent_version)
    agent_kbs = list_agent_kbs_response['agentKnowledgeBaseSummaries']
    # Loop through and process
    for agent_kb in agent_kbs:
        kbs.append({
            'id': agent_kb['knowledgeBaseId'],
            'state': agent_kb['knowledgeBaseState']
        })


def get_br_sub_agents(bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version) -> list[tuple[str, str]]:
    """
    Function to get the sub-agents associated with the specified supervisor agent

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_supervisor_agent_id (str): The id of the Bedrock Agent with a supervisor role
    br_supervisor_agent_version (str): The version of the Bedrock Agent with a supervisor role

    Returns:
    list[tuple[str, str]]: A tuple of sub-agent info
    """
    br_sub_agents = []
    # Get the list of collaborators (sub-agents) associated with the supervisor agent
    list_agent_collaborators_response = bedrock_agt_client.list_agent_collaborators(agentId=br_supervisor_agent_id,
                                                                                    agentVersion=br_supervisor_agent_version)
    agent_collaborators = list_agent_collaborators_response['agentCollaboratorSummaries']
    # Loop through the collaborators list
    for agent_collaborator in agent_collaborators:
        # Get the collaborator agent's details
        agent_collaborator_alias_arn_parts = (agent_collaborator['agentDescriptor']['aliasArn']).split('/')
        agent_collaborator_id = agent_collaborator_alias_arn_parts[1]
        agent_collaborator_alias_id = agent_collaborator_alias_arn_parts[2]
        get_agent_alias_response = bedrock_agt_client.get_agent_alias(agentAliasId=agent_collaborator_alias_id,
                                                                      agentId=agent_collaborator_id)
        agent_collaborator_version = get_agent_alias_response['agentAlias']['routingConfiguration'][0]['agentVersion']
        br_sub_agents.append({'br_sub_agent_id': agent_collaborator_id, 'br_sub_agent_version': agent_collaborator_version})
    return br_sub_agents


def get_kbs(bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version) -> list[str]:
    """
    Function to get the list of KBs associated with the specified agent and all of it's collaborators

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_supervisor_agent_id (str): The id of the Bedrock Agent with a supervisor role
    br_supervisor_agent_version (str): The version of the Bedrock Agent with a supervisor role

    Returns:
    list[str]: An array of KB ids
    """
    # Initialize
    kbs = []
    # Process the supervisor agent kb list
    append_agent_kbs_to_list(kbs, bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version)
    # Get the sub-agents associated with this supervisor agent - One-level down from top
    br_sub_agents = get_br_sub_agents(bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version)
    # Loop through the sub-agents
    for br_sub_agent in br_sub_agents:
        # Process the sub-agent kb list
        append_agent_kbs_to_list(kbs, bedrock_agt_client, br_sub_agent['br_sub_agent_id'], br_sub_agent['br_sub_agent_version'])
        # Get the sub-agents associated with this sub-agent - Two-level down from top
        br_sub_sub_agents = get_br_sub_agents(bedrock_agt_client, br_sub_agent['br_sub_agent_id'], br_sub_agent['br_sub_agent_version'])
        # Loop through the sub-sub-agents
        for br_sub_sub_agent in br_sub_sub_agents:
            # Process the sub-sub-agent kb list
            append_agent_kbs_to_list(kbs, bedrock_agt_client, br_sub_sub_agent['br_sub_agent_id'], br_sub_sub_agent['br_sub_agent_version'])
    # Print the info
    logging.info("Found {} Knowledge Bases(KBs) associated with the specified supervisor agent (id '{} and version '{}') and all it's collaborator agents."
                 .format(len(kbs), br_supervisor_agent_id, br_supervisor_agent_version))
    logging.info("List of KBs :: {}".format(kbs))
    return kbs


def get_kb_data_sources(bedrock_agt_client, kb_id) -> list[str]:
    """
    Function to get the list of data sources associated with the specified Knowledge Base (KB)

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    kb_id (str): The id of the Bedrock Knowledge Base

    Returns:
    list[str]: An array of data source ids
    """
    # Initialize
    data_sources = []
    # Get the list of data sources associated with this KB
    list_data_sources_response = bedrock_agt_client.list_data_sources(knowledgeBaseId=kb_id)
    data_source_summaries = list_data_sources_response['dataSourceSummaries']
    for data_source_summary in data_source_summaries:
        ds_id = data_source_summary['dataSourceId']
        # Get the data source details
        get_data_source_response = bedrock_agt_client.get_data_source(dataSourceId=ds_id, knowledgeBaseId=kb_id)
        data_sources.append({
            'id': ds_id,
            'type': get_data_source_response['dataSource']['dataSourceConfiguration']['type'],
            'status': data_source_summary['status']
        })
    return data_sources


def get_bucket_from_kb_s3_data_source(bedrock_agt_client, kb_id, ds_id) -> list[str]:
    """
    Function to get the Amazon S3 bucket associated with the specified data source in the specified Knowledge Base (KB)

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    kb_id (str): The id of the Bedrock Knowledge Base
    ds_id (str): The id of the S3 data source associated with the Bedrock Knowledge Base

    Returns:
    list[str]: An array of S3 details
    """
    bucket_arn, bucket_name = '', ''
    # Get the data source details
    get_data_source_response = bedrock_agt_client.get_data_source(dataSourceId=ds_id, knowledgeBaseId=kb_id)
    # Get the bucket details
    bucket_arn = get_data_source_response['dataSource']['dataSourceConfiguration']['s3Configuration']['bucketArn']
    bucket_name = get_s3_bucket_name_from_arn(bucket_arn)
    return bucket_arn, bucket_name


def append_agent_lambda_functions_to_list(lambda_functions, bedrock_agt_client, br_agent_id, br_agent_version) -> None:
    """
    Function to retrieve the list of lambda functions associated with the specified agent and append to the specified list

    Parameters:
    lambda_functions (list[str]): The list of lambda function ARNs
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_agent_id (str): The id of the Bedrock Agent
    br_agent_version (str): The version of the Bedrock Agent

    Returns:
    None
    """
    # Get the action groups, if any, associated with the agent
    list_agent_action_groups_response = bedrock_agt_client.list_agent_action_groups(agentId=br_agent_id,
                                                                                    agentVersion=br_agent_version)
    agent_action_groups = list_agent_action_groups_response['actionGroupSummaries']
    # Loop through and process
    for agent_action_group in agent_action_groups:
        # Get the details of the agent action group
        get_agent_action_group_response = bedrock_agt_client.get_agent_action_group(actionGroupId=agent_action_group['actionGroupId'],
                                                                                    agentId=br_agent_id,
                                                                                    agentVersion=br_agent_version)
        # Get the lambda function ARN and name
        agent_action_group = get_agent_action_group_response['agentActionGroup']
        if ('actionGroupExecutor' in agent_action_group) and ('lambda' in agent_action_group['actionGroupExecutor']):
            lambda_function_arn = agent_action_group['actionGroupExecutor']['lambda']
            lambda_function_name = substring_after(lambda_function_arn, ':function:')
            lambda_functions.append(lambda_function_name)


def get_lambda_functions(bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version) -> list[str]:
    """
    Function to get the list of lambda functions associated with the specified agent and all of it's collaborators

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    br_supervisor_agent_id (str): The id of the Bedrock Agent with a supervisor role
    br_supervisor_agent_version (str): The version of the Bedrock Agent with a supervisor role

    Returns:
    list[str]: An array of lambda function ARNs
    """
    # Initialize
    lambda_functions = []
    # Process the supervisor agent action group list
    append_agent_lambda_functions_to_list(lambda_functions, bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version)
    # Get the sub-agents associated with this supervisor agent - One-level down from top
    br_sub_agents = get_br_sub_agents(bedrock_agt_client, br_supervisor_agent_id, br_supervisor_agent_version)
    # Loop through the sub-agents
    for br_sub_agent in br_sub_agents:
        # Process the sub-agent lambda function list
        append_agent_lambda_functions_to_list(lambda_functions, bedrock_agt_client, br_sub_agent['br_sub_agent_id'], br_sub_agent['br_sub_agent_version'])
        # Get the sub-agents associated with this sub-agent - Two-level down from top
        br_sub_sub_agents = get_br_sub_agents(bedrock_agt_client, br_sub_agent['br_sub_agent_id'], br_sub_agent['br_sub_agent_version'])
        # Loop through the sub-sub-agents
        for br_sub_sub_agent in br_sub_sub_agents:
            # Process the sub-sub-agent lambda function list
            append_agent_lambda_functions_to_list(lambda_functions, bedrock_agt_client, br_sub_sub_agent['br_sub_agent_id'], br_sub_sub_agent['br_sub_agent_version'])
    # Remove duplicates
    lambda_functions = list(set(lambda_functions))
    # Print the info
    logging.info("Found {} Lambda Functions associated with the specified supervisor agent (id '{} and version '{}') and all it's collaborator agents."
                 .format(len(lambda_functions), br_supervisor_agent_id, br_supervisor_agent_version))
    logging.info("List of Lambda Functions :: {}".format(lambda_functions))
    return lambda_functions


def ingest_into_kb(bedrock_agt_client, kb_id, kb_ds_id, content_http_url) -> tuple[str, str]:
    """
    Function to ingest the content from the specified URL into the specified Knowledge Base (KB)

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    kb_id (str): The id of the Bedrock Knowledge Base
    kb_ds_id (str): The id of the Bedrock Knowledge Base's data source
    content_http_url (str): The HTTP URL of the content

    Returns:
    tuple[str, str]: Details about the ingestion response
    """
    # Download the content from the HTTP URL
    response = requests.get(content_http_url, timeout=60)
    # Create the KB ingestion request document
    kb_ingest_request_document = {
        'content': {
            'custom': {
                'customDocumentIdentifier': {
                    'id': content_http_url
                },
                'inlineContent': {
                    'textContent': {
                        'data': response.content.decode()
                    },
                    'type': 'TEXT'
                },
                'sourceType': 'IN_LINE'
            },
            'dataSourceType': 'CUSTOM'
        },
        'metadata': {
            'inlineAttributes': [
                {
                    'key': 'ContentURL',
                    'value': {
                        'stringValue': content_http_url,
                        'type': 'STRING'
                    }
                },
            ],
            'type': 'IN_LINE_ATTRIBUTE'
        }
    }
    # Ingest into the KB
    kb_ingest_response = bedrock_agt_client.ingest_knowledge_base_documents(dataSourceId=kb_ds_id,
                                                                            documents=[kb_ingest_request_document],
                                                                            knowledgeBaseId=kb_id)
    response_document_details = kb_ingest_response['documentDetails'][0]
    response_status = response_document_details['status']
    if response_status == 'IGNORED':
        response_status_reason = response_document_details['statusReason']
    else:
        response_status_reason = ''
    # Return the response
    return response_status, response_status_reason


def sync_to_kb(bedrock_agt_client, ds_id, kb_id, job_desc):
    """
    Function to sync data from the specified data source into the specified KB

    Parameters:
    bedrock_agt_client (boto3 client): The boto3 client for Bedrock Agent
    ds_id (string): The id of the data source
    kb_id (string): The id of the Knowledge Base
    job_desc (string): The description for this sync job

    Returns:
    None
    """
    start_ingestion_job_response = bedrock_agt_client.start_ingestion_job(dataSourceId=ds_id,
                                                                          description=job_desc,
                                                                          knowledgeBaseId=kb_id)
    ingestion_job_id = start_ingestion_job_response['ingestionJob']['ingestionJobId']
    logging.info("Ingestion job '{}' started.'".format(ingestion_job_id))
    # Sleep every 5 seconds; retrieve and check the status of the ingestion job
    # until it goes to COMPLETE or FAILED state
    while True:
        get_ingestion_job_response = bedrock_agt_client.get_ingestion_job(dataSourceId=ds_id,
                                                                          ingestionJobId=ingestion_job_id,
                                                                          knowledgeBaseId=kb_id)
        ingestion_job_status = get_ingestion_job_response['ingestionJob']['status']
        logging.info("Ingestion job '{}' is in '{}' status.".format(ingestion_job_id, ingestion_job_status))
        if ingestion_job_status in {'COMPLETE', 'FAILED'}:
            break
        else:
            logging.info("Waiting for 5 seconds to check the status...")
        time.sleep(5)


def serialize_datetime(obj) -> str:
    """
    Function that serializes datetime objects

    Parameters:
    obj (datetime.datetime): The datetime object

    Returns:
    str: The serialized datetime
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError("Datetime type not serializable.")


def invoke_agent(br_agent_alias_id, br_agent_id, bedrock_agt_rt_client, query) -> tuple[str, str]:
    """
    Function that invokes the specified Bedrock agent and it's alias with the specified query

    Parameters:
    br_agent_alias_id (str): The id of the Bedrock Agent Alias
    br_agent_id (str): The id of the Bedrock Agent
    bedrock_agt_rt_client (AgentsforBedrockRuntime.Client): The boto3 client for Bedrock Agent Runtime
    query (str): The query from the user

    Returns:
    str: The response from the agent
    str: The trace associated with the response from the agent
    """
    # Invoke the Bedrock Agent
    logging.info('Invoking Bedrock Agent with id "{}" and alias "{}"...'.format(br_agent_id, br_agent_alias_id))
    start = timer()
    invoke_agent_response = bedrock_agt_rt_client.invoke_agent(
        agentAliasId=br_agent_alias_id,
        agentId=br_agent_id,
        enableTrace=True,
        endSession=False,
        inputText=query,
        sessionId=str(uuid.uuid4())
    )
    completion = ''
    trace = ''
    # Process the chunk and trace parts of the response
    for event in invoke_agent_response.get('completion'):
        logging.debug(event)
        # Check if the 'chunk' object exists and read it
        if 'chunk' in event:
            chunk = event['chunk']
            completion += chunk['bytes'].decode()
        # Check if the 'trace' object exists and read it
        if 'trace' in event:
            trace_part = event['trace']
            trace += json.dumps(trace_part, default=serialize_datetime) + ','
    end = timer()
    logging.info('Completed invoking Bedrock Agent.')
    logging.info('Prompt processing duration = {} second(s)'.format(end - start))
    return completion, trace
