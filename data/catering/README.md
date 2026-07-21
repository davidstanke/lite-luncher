In this folder, `catering_menu.json` contains data which can be imported to BigQuery. To make available over MCP:

* Import to a BQ table: `<project_id>.catering.menu-items`
* Grant query access to `allUsers` on that table [todo: be more secure about this]
* Grant the following roles to the service account identity of the Agent Runtime agent(s) which will invoke it:
  * `roles/mcp.toolUser`
  * `roles/bigquery.jobUser`
  * `roles/bigquery.dataViewer`
  