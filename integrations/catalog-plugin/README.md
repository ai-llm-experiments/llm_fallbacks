# LLM Fallbacks catalog plugin candidate

A local, read-only MCP server searches a bundled snapshot of `configs/free_models.json` from [llm_fallbacks](https://github.com/ai-llm-experiments/llm_fallbacks). It makes no network requests, accesses no credentials, changes no routes and runs no inference. Each result includes source commit, date and catalog SHA-256. Snapshot information can be stale or wrong: a free label or heuristic score is not proof of current price, eligibility, model quality, privacy or availability. Verify against the actual provider and account before using a model. The original ordering is preserved, including any pinned entries.

Requires Node.js 18 or newer. Update the catalog, provenance constants and version together when preparing a release. This is a review candidate; neither client installation nor client-launched MCP startup has been verified. The MCPB manifest passed the official MCPB 2.1.2 validator, and the portable manifests passed their published JSON schemas.

## Codex

The portable `plugin.json` and `mcp.json` describe a desktop-only plugin with a local stdio MCP server. The plugin has no hooks and requests no secret. To make a checkout available as a local marketplace, create `.agents/plugins/marketplace.json` at the checkout root:

```json
{
  "name": "llm-fallbacks-local",
  "plugins": [{
    "name": "llm-fallbacks-catalog",
    "source": {"source": "local", "path": "./integrations/catalog-plugin"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools"
  }]
}
```

From that checkout root, list the plugin without installing it or changing Codex user configuration:

```sh
codex -c 'marketplaces.llm-fallbacks-local.source_type="local"' \
  -c 'marketplaces.llm-fallbacks-local.source="."' \
  plugin list --marketplace llm-fallbacks-local --available --json
```

The local source and entry name must match the marketplace configuration. Codex CLI 0.169.0 discovered an equivalent isolated marketplace using explicit command-line configuration; automatic discovery of the unregistered repository marketplace did not occur in that check. A listing with `installed: false` proves discovery only. Follow the [OpenAI packaging guide](https://developers.openai.com/plugins/build/plugins) to register a marketplace or install through a supported client. Installing changes client state; successful tool startup has not yet been verified. Paths in a marketplace are relative to its root and must remain inside it.

## Claude Desktop

Create a bundle using the [MCPB tool](https://github.com/modelcontextprotocol/mcpb) from this directory (`mcpb pack`) and install the resulting `.mcpb` through the [custom desktop extension flow](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). The bundle includes `manifest.json`, `server/index.js` and `data/free_models.json`; it has no npm dependencies. Claude Desktop extension support and policies depend on platform and organization configuration. Validate the manifest and bundle with the official tool before distributing it.

## Tool

`search_catalog` accepts optional `query` (model/provider substring), `mode` (exact value), `requires_tools` (boolean), and `limit` (1–100, default 20). Results preserve snapshot order; `total_matches` is the count before the limit. No tool changes the catalog. This adapter is informational only; it does not provide automatic failover or OmniRoute synchronization.
