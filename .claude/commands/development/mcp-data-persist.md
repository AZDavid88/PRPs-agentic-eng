# MCP Data Persistence

Use Upstash MCP server for state management and data persistence across PRP sessions.

## Usage
`/mcp-data-persist [action] [key] [data]`

## Description
Leverages Upstash MCP server to store and retrieve state data across PRP execution sessions. Enables persistent context, progress tracking, and shared data between multiple PRP runs.

**Configured with:**
- Email: david.tran.int@gmail.com  
- API Key: 34a3f14d-67f7-4962-bcea-2c2dacadfdf4 (Note: Key needs validation - may be expired)

**Setup Requirements:**
1. Get valid Upstash API key from https://console.upstash.com/
2. Update UPSTASH_API_KEY in `.claude/settings.local.json`
3. Test connection with: `npx -y @upstash/mcp-server run [email]`

## Parameters
- `action`: Operation type (store, retrieve, update, delete, list)
- `key`: Unique identifier for the data
- `data`: Data to store (for store/update operations)

## Process
1. Connect to Upstash Redis via MCP server
2. Execute specified data operation
3. Handle response and error cases
4. Return operation result and status

## Use Cases
- Store PRP execution progress and state
- Share data between parallel PRP sessions
- Cache expensive computations and API results
- Track validation results across iterations
- Maintain session context for complex workflows

## Integration
- Automatically used by PRP runner for progress tracking
- Available in all PRP templates for state management
- Supports distributed PRP execution workflows

## Examples
```
/mcp-data-persist "store" "prp-auth-progress" '{"completed": ["validation", "tests"], "next": "deployment"}'
/mcp-data-persist "retrieve" "prp-auth-progress"
/mcp-data-persist "list" "prp-*"
```