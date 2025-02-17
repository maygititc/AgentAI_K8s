import os
from langgraph.core.agent import Agent, run_agent
from langgraph.utils.http_client import HTTPClient

# Define the service and port where the logs are being emitted
SERVICE = "your-service-name"
PORT = 8080

def process_logs(args):
    """Process log lines and return tagged events."""
    # Tokenize each line into events
    tokens = args.split('\n')
    for token in tokens:
        if not token.strip():
            continue
        
        # Tokenize the log line (basic example)
        event, context = tokenize_log(token)
        
        yield f"{event}, {context}"

def tokenize_log(log_line):
    """Simple tokenizer that groups logs into events."""
    operator_tokens = ['kubeadm', 'kubectl', 'exit']
    
    words = log_line.split()
    event = []
    current_token = None
    
    for word in words:
        if word in operator_tokens or len(word) < 3:
            # Start a new event
            event = [word]
            continue
        
        if not event[-1]:
            event.append(word)
        else:
            if (len(event[-1]) > 0 and 
                any(t.lower() in event[-1].lower() for t in operator_tokens)):
                event[-1] += ' ' + word
            else:
                event.append(word)
    
    # Determine the context based on tokens found in line
    context = []
    for token in ['kubeadm', 'kubectl', 'exit']:
        if token in log_line.lower():
            context.append(token)
    
    return ' '.join(event), ', '.join(context)

def send_event(args, event_type, context):
    """Sends processed events to Kubeadm via Redis."""
    try:
        http_client = HTTPClient()
        http_client.send(
            f"{event_type}: {context}", 
            from_env=True
        )
    except Exception as e:
        print(f"Error sending event: {e}")

def send_alert(args, error):
    """Sends alerts to Kubeadm when errors occur."""
    try:
        http_client = HTTPClient()
        http_client.send(
            f"alert: {error}",
            from_env=True
        )
    except Exception as e:
        print(f"Error sending alert: {e}")

def run_agent_env():
    """Main environment for the agent to run in."""
    os.environ["KUBERNETES_SERVICE"] = SERVICE
    os.environ["KUBERNETES_PORT"] = str(PORT)
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    client = HTTPClient()
    httpd = client.create_httpd(port=PORT)

    try:
        agent = run_agent(
            name="log-monitor-agent",
            process=process_logs,
            send=send_event,
            env=env,
            httpd=httpd
        )

        while True:
            line = httpd.read().decode()
            if not line.strip():
                continue
            logger.info(f"Processing log: {line}")
            
            try:
                event_type, context = process_logs([line])
                send_event(args=event_type, args=event_type, event_type=event_type, context=context)
                
                # Simple alerting system
                if "error" in line.lower():
                    error = extract_error(line)
                    send_alert(error=error)

            except Exception as e:
                logger.error(f"Error processing log: {e}")

    except KeyboardInterrupt:
        print("\nShutting down agent...\n")
    
    finally:
        httpd.close()

if __name__ == "__main__":
    run_agent_env()
