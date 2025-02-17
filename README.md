"# AgentAI_K8s" 


✅ Advanced Log Filtering:

Filters logs based on ERROR, WARN, and other keywords.
Limits logs to the last 100 lines for efficiency.

✅ Multiple Kubernetes Tools Support:

Detects kubectl, kubeadm, calicoctl, and executes appropriate commands.
Parses LLM suggestions to decide which tool to use.

✅ Automated Fix Execution:

Extracts the exact command from the LLM response.
Runs it automatically and reports the results.

✅ Slack Notifications

Sends alerts when an issue is detected and fixed.
Uses Slack webhook for real-time updates.

✅ Email Alerts

Sends an email summary with issue details and applied fixes.
Uses SMTP for email delivery.

✅ Improved Log Filtering

Detects errors and warnings automatically.
Limits logs to the last 100 lines to improve efficiency.

✅ Automated Fix Execution

Determines the right tool (kubectl, kubeadm, calicoctl).
Runs the fix automatically and reports the results via Slack & email.

✅ Grafana Alerts Integration

Sends alerts to Grafana using Webhook API.
Can be configured to trigger Grafana Alert Manager notifications.

✅ Slack & Email Alerts

Sends notifications when issues are detected and fixed.

✅ Fully Automated Troubleshooting

Detects errors, suggests fixes, and executes them automatically.
Uses kubectl, kubeadm, and calicoctl for issue resolution.