# 1- receive message from chatwoot
# 2- save to the table messages
# 3- create session if not exists
# 4- retrieve history from db
# 5- check if is a message that requires rag or just a chat/ simple conversation
# 5- If requires rag, send to rag
# 6- receive response from rag
# 7- send the message to llm so it can create the final answer
# 8- save to the table messages
# 9- send to chatwoot
