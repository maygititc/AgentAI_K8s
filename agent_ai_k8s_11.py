import time
import subprocess
import json
import openai
import re
from langgraph.graph import StateGraph
from kubernetes import client, config

# Load Kubernetes config
config.load_kube_config()

# OpenAI API Key (Replace with your key)
OPENAI_API_KEY = "your-openai-api-key"

# Function to get filtered logs from all pods
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

# Function to send logs to LLM for analysis
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

# Function to determine which tool to use based on LLM output
def fix_issues(state):
    suggested_fixes = state["analysis"]
    
    # Extract commands
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
        return {"fix": fix_result}
    
    return {"fix": "No actionable fix suggested"}

# Define LangGraph workflow
class KubernetesState:
    logs: dict
    analysis: str
    fix: str

def kubernetes_workflow():
    graph = StateGraph(KubernetesState)
    
    # Node to get logs with filtering
    graph.add_node("fetch_logs", lambda state: {
        "logs": get_filtered_k8s_logs(filter_keywords=["ERROR", "WARN"], last_n_lines=100)
    })
    
    # Node to analyze logs
    graph.add_node("analyze_logs", lambda state: {"analysis": analyze_logs_with_llm(state["logs"])})
    
    # Node to fix issues using appropriate Kubernetes tool
    graph.add_node("fix_issues", fix_issues)
    
    # Define workflow edges
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
