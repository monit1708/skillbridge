from flask_login import current_user
from flask_socketio import emit, join_room
from .extensions import db
from .models import Conversation, Message

def register_chat(socketio):
    @socketio.on('join')
    def on_join(data):
        if not current_user.is_authenticated: return
        try: cid=int(data.get('conversation_id'))
        except (ValueError,TypeError,AttributeError): return
        conv=db.session.get(Conversation,cid)
        if not conv or current_user.id not in (conv.exchange.request.sender_id,conv.exchange.request.receiver_id): return
        join_room(f'conversation:{cid}')
        emit('joined', {'conversation_id':cid})
    @socketio.on('message')
    def on_message(data):
        if not current_user.is_authenticated: return
        try: cid=int(data.get('conversation_id'))
        except (ValueError,TypeError,AttributeError): return
        body=str(data.get('body','')).strip()
        conv=db.session.get(Conversation,cid)
        if not conv or current_user.id not in (conv.exchange.request.sender_id,conv.exchange.request.receiver_id) or not body or len(body)>2000: return
        message=Message(conversation_id=cid,sender_id=current_user.id,body=body); db.session.add(message); db.session.commit()
        emit('message', {'id':message.id,'sender':current_user.name,'sender_id':current_user.id,'body':body,'created_at':message.created_at.isoformat()}, room=f'conversation:{cid}')
