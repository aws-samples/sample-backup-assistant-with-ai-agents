## Plan, strategize, and automate AWS Backup with AI Agents on Amazon Bedrock

This repository contains code samples that will show you how to use [Amazon Bedrock Agents](https://aws.amazon.com/bedrock/agents/) along with the [Large Language Models (LLMs)](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html) on Amazon Bedrock to provide an easy-to-use natural language interface to strategize, plan, and execute your data backup objectives using [AWS Backup](https://aws.amazon.com/backup/).

### Overview

[AWS Backup](https://aws.amazon.com/backup/) is a fully managed backup service centralizing and automating the backup of data across AWS services. AWS Backup provides an orchestration layer that integrates Amazon CloudWatch, AWS CloudTrail, AWS Identity and Access Management (IAM), AWS Organizations, and other services. This centralized, AWS Cloud native solution provides global backup capabilities that can help you achieve your disaster recovery and compliance requirements. Using AWS Backup, you can centrally configure backup policies and monitor backup activity for AWS resources.

When creating a data backup strategy, you will need to understand the concepts, best practices, and architecture principles behind data backup and recovery. You would want to make sure all your resources are covered. While these can be challenging, configuring AWS Backup for your backup objectives requires knowledge of AWS Backup APIs, and how to invoke one or more of them in a sequence based on your requirements. AI agents can help with all these.

### To get started

1. Choose an AWS Account to use and make sure to create all resources in that Account.
2. Identify an AWS Region that has [Amazon Bedrock with Anthropic Claude 3.5 Haiku v1, Anthropic Claude 3.5 Sonnet v2 / 3.7 Sonnet v1, and Amazon Titan Text Embeddings v2](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html) models.
3. In that Region, copy the following file to a new or existing [Amazon S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingBucket.html) of your choice. Make sure that this bucket can be read by [AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html).
   * [backup-assistant-agent-handler.zip](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets/dependencies/backup-assistant-agent-handler.zip)
4. Create the Lambda layer file named `py313_opensearch-py_requests_and_requests-aws4auth.zip` using the following procedure and upload it to the same Amazon S3 bucket as in step 3.
   - On Windows 10 or above:
     1. Make sure [Python 3.13](https://docs.python.org/3/whatsnew/3.13.html) and [pip](https://pip.pypa.io/en/stable/installation/) are installed and set in the user's PATH variable.
     2. Download [7-zip](https://www.7-zip.org/) and install it in `C:/Program Files/7-Zip/`.
     3. Open the Windows command prompt.
     4. Create a new directory and `cd` into it.
     5. Run the [lambda_layer_file_create.bat](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets/dependencies/lambda_layer_file_create.bat) from inside of that directory.
     6. This will create the Lambda layer file named `py313_opensearch-py_requests_and_requests-aws4auth.zip`.
   - On Linux:
     1. Make sure [Python 3.13](https://docs.python.org/3/whatsnew/3.13.html) and [pip](https://pip.pypa.io/en/stable/installation/) are installed and set in the user's PATH variable.
     2. Open the Linux command prompt.
     3. Create a new directory and `cd` into it.
     4. Run the [lambda_layer_file_create.sh](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets/dependencies/lambda_layer_file_create.sh) from inside of that directory.
     5. This will create the Lambda layer file named `py313_opensearch-py_requests_and_requests-aws4auth.zip`.
5. Take the provided AWS CloudFormation template [backup-assistant-with-ai-agents-cfn.yaml](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets/backup-assistant-with-ai-agents-cfn.yaml) and update the following parameter,
   * *DeploymentArtifactsS3BucketName* - set this to the name of the Amazon S3 bucket from step 3.
6. Create an [AWS CloudFormation stack](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-whatis-concepts.html#cfn-concepts-stacks) with the updated template.
7. Open the Jupyter notebook named *aws-backup-automation-with-ai-agents.ipynb* by navigating to the [Amazon SageMaker AI notebook instances console](https://docs.aws.amazon.com/sagemaker/latest/dg/howitworks-access-ws.html) and clicking on the *Open Jupyter* link on the instance named *backup-assistant-instance*.

### Repository structure

This repository contains

* [An assets folder](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets) that contains the AWS CloudFormation template and the dependent  artifacts.
* [The Python code for an AWS Lambda function](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/lambda) that will be invoked by the Bedrock Agent to perform the supported AWS Backup operations. This is also zipped into [this file](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/assets/dependencies/backup-assistant-agent-handler.zip) as a dependent artifact.
* [A notebooks folder](https://github.com/aws-samples/sample-backup-assistant-with-ai-agents/blob/main/notebooks) that contains all the artifacts related to the Jupyter notebook that you will be working on.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

