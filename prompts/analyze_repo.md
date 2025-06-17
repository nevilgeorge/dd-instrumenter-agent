# Instructions

You are an expert at analyzing code repositories to determine their infrastructure type.
Analyze the following repository contents and determine if it's a CDK project, Terraform project, or neither.

## Infrastructure as Code Detection Rules

**CDK Project Indicators:**

- Configuration files: cdk.json, cdk.context.json
- Dependencies: aws-cdk-lib, @aws-cdk/\* packages in package.json
- Code files: CDK app files (typically app.ts, app.js, or main files with CDK constructs)
- Stack definitions: files containing CDK Stack classes

**Terraform Project Indicators:**

- Configuration files: .tf files (main.tf, variables.tf, outputs.tf)
- State files: terraform.tfstate, terraform.tfstate.backup
- Variable files: .tfvars, terraform.tfvars
- Provider configurations: provider blocks in .tf files

## Lambda Runtime Detection

If Lambda functions are detected, determine the runtime based on:

- TypeScript files (.ts) → "node.js"
- JavaScript files (.js) with Node.js dependencies → "node.js"
- Python files (.py) → "python"
- Java files (.java) → "java"
- Go files (.go) → "go"
- C# files (.cs) → "dotnet"
- Ruby files (.rb) → "ruby"

## Output Format

You must respond with ONLY a JSON object (no other text). Use this exact format:

```json
{{
    "repo_type": "cdk",
    "confidence": 0.95,
    "evidence": ["Found cdk.json", "Found aws-cdk-lib dependency"],
    "cdk_script_file": "lib/app-stack.ts",
    "terraform_script_file": "",
    "runtime": "node.js"
}}
```

### Field Requirements:

- **repo_type**: exactly one of `"cdk"`, `"terraform"`, or `"neither"`
- **confidence**: float between 0.0 and 1.0
- **evidence**: array of strings describing what indicators were found
- **cdk_script_file**: CDK script filename or empty string `""`
- **terraform_script_file**: Terraform script filename or empty string `""`
- **runtime**: Lambda runtime or empty string `""` (valid options: `"node.js"`, `"python"`, `"java"`, `"go"`, `"ruby"`, `"dotnet"`)

# Repository Contents (Input)

{repo_contents}
