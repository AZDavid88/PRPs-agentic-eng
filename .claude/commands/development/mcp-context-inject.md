# MCP Context Injection

Use Context7 MCP server to inject real-time documentation and codebase intelligence into current context.

## Usage
`/mcp-context-inject [query] [scope]`

## Description
Leverages the Context7 MCP server to dynamically fetch relevant documentation, code examples, and contextual information based on your query. This enhances PRP creation and execution with live codebase intelligence.

**Available Tools:**
- `resolve-library-id`: Convert library name to Context7-compatible ID
- `get-library-docs`: Fetch documentation for specific library ID

**Setup:** Local server via `npx -y @upstash/context7-mcp` (stdio transport)

## Parameters
- `query`: Search terms or topics to find relevant context
- `scope`: Optional scope (docs, examples, patterns, all)

## Process
1. Query Context7 MCP server with search terms
2. Retrieve relevant documentation and code patterns  
3. Inject context into current session
4. Provide formatted output for PRP enhancement

## Integration
- Automatically called during PRP creation for comprehensive context
- Can be used standalone for research and understanding
- Integrates with existing PRP templates and validation loops

## Examples
```
/mcp-context-inject "authentication patterns" "examples"
resolve-library-id "nextjs"
get-library-docs "/vercel/next.js" "routing"
```

**Pro Tips from README:**
- Add library ID directly: `use library /supabase/supabase for api and docs`  
- Add `use context7` to any prompt for automatic documentation injection
- Use exact Context7 IDs (e.g. `/mongodb/docs`, `/vercel/next.js`) to skip library matching