# MCP Web Validation

Use Puppeteer MCP server for automated web testing and validation in PRP workflows.

## Usage
`/mcp-web-validate [url] [test-type]`

## Description
Leverages Puppeteer MCP server to perform automated browser-based testing and validation. Ideal for end-to-end testing of web applications, form validation, and user journey verification.

## Parameters
- `url`: Target URL to test
- `test-type`: Type of validation (form, navigation, performance, accessibility)

## Process
1. Launch browser instance via Puppeteer MCP
2. Navigate to target URL
3. Execute specified test scenarios
4. Capture results, screenshots, and performance metrics
5. Return validation status and detailed report

## Integration
- Used in PRP validation loops for web-based applications
- Can validate implementation against user requirements
- Provides automated testing for CI/CD integration

## Example
```
/mcp-web-validate "http://localhost:3000/login" "form"
```

This will test the login form functionality, validate field requirements, submit behavior, and error handling.