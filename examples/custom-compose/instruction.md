## Goal

Verify that the custom Docker Compose environment is active by checking the
`CUSTOM_ENV` environment variable and writing its value to a file.

## Requirements

- Read the `CUSTOM_ENV` environment variable
- Write its value to `/workspace/env-check.txt`
- The value should be "from-compose" (set in the custom compose.yaml)

## Constraints

- Do not hardcode the value — read it from the environment
- Do not modify the compose.yaml file
- Do not create any files other than `/workspace/env-check.txt`

## Output

Success criteria:
- File `/workspace/env-check.txt` exists
- Content is "from-compose"
