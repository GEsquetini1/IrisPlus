import asyncio
import websockets
import json
import time
from datetime import datetime

class EyeTrackingServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.connected_clients = set()
        
    async def handler(self, websocket, path):
        # Registrar novo cliente
        self.connected_clients.add(websocket)
        print(f"Cliente conectado. Total: {len(self.connected_clients)}")
        
        try:
            # Manter conexão aberta
            await websocket.wait_closed()
        finally:
            # Remover cliente ao desconectar
            self.connected_clients.remove(websocket)
            print(f"Cliente desconectado. Total: {len(self.connected_clients)}")
    
    async def broadcast_data(self, data):
        """Envia dados para todos os clientes conectados"""
        if self.connected_clients:
            message = json.dumps(data)
            await asyncio.gather(
                *[client.send(message) for client in self.connected_clients],
                return_exceptions=True
            )
    
    async def start_server(self):
        """Inicia o servidor WebSocket"""
        print(f"Servidor WebSocket iniciado em ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()  # Executar eternamente

# Servidor global para acesso fácil
eye_tracking_server = EyeTrackingServer()