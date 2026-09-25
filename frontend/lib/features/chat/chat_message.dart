import '../../services/chat/chat_service.dart';

/// One entry in the chat transcript.
class ChatMessage {
  const ChatMessage.user(this.text)
      : isUser = true,
        reply = null;

  ChatMessage.assistant(ChatReply reply)
      : text = reply.text,
        isUser = false,
        reply = reply;

  final String text;
  final bool isUser;
  final ChatReply? reply;
}