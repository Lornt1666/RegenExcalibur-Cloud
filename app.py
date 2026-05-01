# Import necessary libraries
import streamlit as st
from fastapi import FastAPI
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Define whitelisted commands
whitelisted_commands = ['command1', 'command2']

# Define a command validation function
def is_command_allowed(command):
    return command in whitelisted_commands

# Define an endpoint that can be called from Streamlit
@app.get('/run-command')
async def run_command(command: str):
    if is_command_allowed(command):
        logger.info(f'Executing command: {command}')
        # Execute the command (this is placeholder logic)
        return {'status': 'success', 'command': command}
    else:
        logger.warning(f'Command not allowed: {command}')
        return {'status': 'error', 'message': 'Command not allowed'}

# Streamlit app
st.title('Agentic Terminal')
command = st.text_input('Enter command')
if st.button('Run'):
    response = await run_command(command)
    st.write(response)

# Display logs
st.subheader('Logs')
with st.expander('View logs'):
    log_stream = open('path_to_logs', 'r')
    st.text(log_stream.read())
    log_stream.close()