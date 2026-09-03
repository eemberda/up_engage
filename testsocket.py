import websocket

if __name__ == '__main__':
    ws = websocket.create_connection("wss://up.copewithtech.com/ws/event/8Z36/")
    print("Connected")
    ws.close()