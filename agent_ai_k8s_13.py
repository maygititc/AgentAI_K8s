import time
import subprocess
import json
import openai
import re
import smtplib
import requests
from email.mime.text import MIMEText
from langgraph.graph import StateGraph
from kubernetes import client, config

# Load Kubernetes config
config.load_kube_config()

# OpenAI API Key (Replace with your key)
OPENAI_API_KEY = "your-openai-api-key"

# Slack Webhook URL
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Email Settings
SMTP_SERVER = "smtp.your-email-provider.com"
SMTP_PORT = 587
EMAIL_SENDER = "your-email@example.com"
EMAIL_PASSWORD = "your-email-password"
EMAIL_RECIPIENT = "recipient@example.com"

# Grafana Webhook URL
GRAFANA_ALERT_WEBHOOK = "http://your-grafana-server.com/api/alert-notifications"

# Function to send Grafana alerts
def send_grafana_alert(title, message):
    payload = {
        "title": title,
        "message": message,
        "severity": "critical"
    }
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(GRAFANA_ALERT_WEBHOOK, json=payload, headers=headers)
    return response.status_code == 200

# Function to send Slack notifications
def send_slack_alert(message):
    payload = {"text": message}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return response.status_code == 200

# Function to send email notifications
def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

# Function to get filtered logs
def get_filtered_k8s_logs(namespace="default", filter_keywords=None, last_n_lines=50):
    v1 = client.CoreV1Api()
    logs = {}
    pods = v1.list_namespaced_pod(namespace).items

    for pod in pods:
        pod_name = pod.metadata.name
        try:
            log = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=last_n_lines)
            if filter_keywords:
                log_lines = log.split("\n")
                filtered_logs = [line for line in log_lines if any(keyword in line for keyword in filter_keywords)]
                logs[pod_name] = "\n".join(filtered_logs)
            else:
                logs[pod_name] = log
        except Exception as e:
            logs[pod_name] = f"Error fetching logs: {str(e)}"
    
    return logs

# Function to analyze logs with LLM
def analyze_logs_with_llm(logs):
    prompt = f"Analyze these Kubernetes logs and suggest fixes:\n{json.dumps(logs, indent=2)}"
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a Kubernetes troubleshooting assistant."},
                  {"role": "user", "content": prompt}]
    )
    
    return response["choices"][0]["message"]["content"]

# Function to execute Kubernetes control commands
def execute_k8s_tool_command(tool, command):
    full_command = f"{tool} {command}"
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return str(e)

# Function to determine tool and command from LLM response
def fix_issues(state):
    suggested_fixes = state["analysis"]
    
    tool_mapping = {
        "kubectl": "kubectl",
        "kubeadm": "kubeadm",
        "calicoctl": "calicoctl"
    }
    
    tool = None
    command = None
    for keyword, tool_name in tool_mapping.items():
        match = re.search(f"{keyword} (.+)", suggested_fixes)
        if match:
            tool = tool_name
            command = match.group(1)
            break

    if tool and command:
        fix_result = execute_k8s_tool_command(tool, command)
        
        # Alert message
        alert_message = f"Kubernetes issue detected and fixed.\n\nSuggested Fix:\n{command}\n\nExecution Result:\n{fix_result}"
        
        # Send alerts
        send_slack_alert(alert_message)
        send_email_alert("Kubernetes Issue Resolved", alert_message)
        send_grafana_alert("Kubernetes Issue Resolved", alert_message)
        
        return {"fix": fix_result}
    
    return {"fix": "No actionable fix suggested"}

# Define LangGraph workflow
class KubernetesState:
    logs: dict
    analysis: str
    fix: str

def kubernetes_workflow():
    graph = StateGraph(KubernetesState)
    
    graph.add_node("fetch_logs", lambda state: {
        "logs": get_filtered_k8s_logs(filter_keywords=["ERROR", "WARN"], last_n_lines=100)
    })
    
    graph.add_node("analyze_logs", lambda state: {"analysis": analyze_logs_with_llm(state["logs"])})
    
    graph.add_node("fix_issues", fix_issues)
    
    graph.add_edge("fetch_logs", "analyze_logs")
    graph.add_edge("analyze_logs", "fix_issues")
    
    return graph

# Main loop to run every 2 minutes
def main():
    workflow = kubernetes_workflow()
    
    while True:
        state = workflow.run({})
        print("Kubernetes Log Analysis Report:\n", state)
        time.sleep(120)  # Wait 2 minutes

if __name__ == "__main__":
    main()
