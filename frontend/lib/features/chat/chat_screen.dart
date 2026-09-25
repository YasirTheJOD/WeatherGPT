import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../l10n/app_localizations.dart';
import '../../models/location.dart';
import '../../services/chat/chat_service.dart';
import '../../services/chat/sse_chat_service.dart';
import '../../services/speech/speech_service.dart';
import '../../state/app_state.dart';
import '../alerts/widgets/alert_card.dart';
import '../weather/widgets/current_conditions_card.dart';
import '../weather/widgets/forecast_strip.dart';
import 'chat_message.dart';
import 'widgets/message_bubble.dart';

/// Chat tab — the conversational core.
///
/// The UI renders whatever [ChatService] returns: text bubbles, weather/alert
/// cards, source attribution, and follow-up chips. The default is the
/// [SseChatService] — the backend `/chat` pipeline (query understanding +
/// orchestrator + LLM) over SSE — which falls back to the deterministic
/// typed endpoints when the backend is unreachable, so the demo never dies.
///
/// Answers are rendered **as they stream**: the SSE `delta` events grow a
/// transient draft bubble (with a caret), which the `done` reply replaces once
/// the cards and provenance are known. A non-streaming service emits no
/// deltas and simply shows the typing indicator until its reply lands.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.chatService, this.speechService});

  final ChatService? chatService;
  final SpeechService? speechService;

  /// Starter questions shown in the empty welcome state — also the exact demo
  /// prompts, including the Hinglish one.
  static const starterPrompts = [
    "What's the weather in Kolkata?",
    'Will it rain tomorrow in Mumbai?',
    'Alerts near me',
    'Kal shaam Mumbai mein baarish hogi kya?',
  ];

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final ChatService _chat = widget.chatService ?? SseChatService();
  late final SpeechService _speech =
      widget.speechService ?? createSpeechService();

  final List<ChatMessage> _messages = [];
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();

  /// A request is in flight — the input stays disabled until the answer lands.
  bool _busy = false;

  /// Partial answer text while an SSE answer streams in; null when idle.
  ///
  /// Deliberately *not* an entry in [_messages]: the transcript only ever holds
  /// completed turns, so an interrupted or superseded answer can never leave a
  /// half-written bubble behind.
  String? _draft;

  bool _listening = false;

  /// The spinner is only for the wait *before* the first token.
  bool get _waiting => _busy && _draft == null;

  /// Shown when a stream ends without ever delivering a reply.
  static const _noReply = ChatReply(
    text: 'Sorry — something went wrong. Please try again.',
  );

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send(String raw, {bool viaVoice = false}) async {
    final text = raw.trim();
    if (text.isEmpty || _busy) return;
    final currentLocation = context.read<AppState>().location;
    _input.clear();
    setState(() {
      _messages.add(ChatMessage.user(text));
      _busy = true;
    });
    _scrollToBottom();

    final reply = await _stream(
      _chat.stream(text, currentLocation: currentLocation),
    );
    if (!mounted) return;
    if (reply.location != null) {
      context.read<AppState>().setLocation(reply.location!);
    }
    setState(() {
      _messages.add(ChatMessage.assistant(reply));
      _busy = false;
      _draft = null;
    });
    // Voice query → speak the answer back (the voice loop demo).
    if (viaVoice && reply.text.isNotEmpty) {
      final localeCode = context.read<AppState>().language.localeCode;
      _speech.speak(reply.text, lang: localeCode);
    }
    _scrollToBottom();
  }

  /// Mic flow: listen → fill nothing, auto-send the transcript → speak reply.
  Future<void> _listenAndSend() async {
    if (_listening) {
      _speech.stop();
      setState(() => _listening = false);
      return;
    }
    if (!_speech.isSupported) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).voiceUnsupported)),
      );
      return;
    }
    setState(() => _listening = true);
    final localeCode = context.read<AppState>().language.localeCode;
    try {
      final transcript = await _speech.listen(lang: localeCode);
      if (!mounted) return;
      setState(() => _listening = false);
      if (transcript.trim().isNotEmpty) {
        await _send(transcript, viaVoice: true);
      }
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _listening = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    }
  }

  /// Drains a streaming answer: every [ChatDelta] grows the draft bubble, and
  /// the [ChatDone] reply — cards, source and suggestions included — replaces
  /// it in the transcript.
  ///
  /// A service that cannot stream (the default [ChatService.stream]) emits a
  /// single [ChatDone], so this degrades to the old "spinner, then the whole
  /// answer" behaviour with no special-casing.
  ///
  /// Implemented as `listen` + a [Completer] rather than `await for` with an
  /// early `return`: exiting an `await for` awaits the subscription teardown,
  /// which pushes the reply past the `done` event that carried it.
  Future<ChatReply> _stream(Stream<ChatStreamEvent> events) {
    final answer = Completer<ChatReply>();
    events.listen(
      (event) {
        switch (event) {
          case ChatDelta(:final text):
            if (!mounted) return;
            setState(() => _draft = _draft == null ? text : '$_draft $text');
            _scrollToBottom();
          case ChatDone(:final reply):
            if (!answer.isCompleted) answer.complete(reply);
        }
      },
      onError: (Object error) {
        if (!answer.isCompleted) {
          answer.complete(
            ChatReply(text: 'Sorry — something went wrong ($error).'),
          );
        }
      },
      onDone: () {
        if (!answer.isCompleted) answer.complete(_noReply);
      },
    );
    return answer.future;
  }

  Future<void> _pickCandidate(ChatReply original, LocationCandidate candidate) async {
    setState(() => _busy = true);
    _scrollToBottom();

    ChatReply reply;
    try {
      reply = await _chat.answerForLocation(original.intent, candidate);
    } on Exception catch (e) {
      reply = ChatReply(text: 'Sorry — something went wrong ($e).');
    }
    if (!mounted) return;
    if (reply.location != null) {
      context.read<AppState>().setLocation(reply.location!);
    }
    setState(() {
      _messages.add(ChatMessage.assistant(reply));
      _busy = false;
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final appState = context.watch<AppState>();

    return Column(
      children: [
        if (appState.location != null)
          Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: InputChip(
                avatar: Icon(Icons.place, size: 16, color: theme.colorScheme.primary),
                label: Text(appState.location!.name),
                visualDensity: VisualDensity.compact,
                onPressed: null,
              ),
            ),
          ),
        Expanded(
          child: _messages.isEmpty
              ? _Welcome(l10n: l10n, theme: theme, onPrompt: _send)
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  // The transient draft rides at the end of the transcript
                  // without ever being committed to it.
                  itemCount: _messages.length + (_draft == null ? 0 : 1),
                  itemBuilder: (context, index) => index < _messages.length
                      ? _buildMessage(_messages[index])
                      : _buildDraft(_draft!),
                ),
        ),
        if (_waiting)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Text(l10n.typing, style: theme.textTheme.bodySmall),
                ],
              ),
            ),
          ),
        if (_listening)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.graphic_eq,
                      size: 16, color: theme.colorScheme.error),
                  const SizedBox(width: 8),
                  Text(l10n.listening, style: theme.textTheme.bodySmall),
                ],
              ),
            ),
          ),
        _InputBar(
          controller: _input,
          enabled: !_busy && !_listening,
          hint: l10n.chatHint,
          sendTooltip: l10n.send,
          micTooltip: _listening ? l10n.stopListeningTooltip : l10n.micTooltip,
          listening: _listening,
          onSend: _send,
          onMic: _listenAndSend,
        ),
      ],
    );
  }

  /// The in-flight answer: an assistant bubble that grows as deltas arrive,
  /// with a caret so a stalled stream is never mistaken for a finished reply.
  Widget _buildDraft(String text) => MessageBubble(
        message: ChatMessage.assistant(ChatReply(text: '$text ▍')),
      );

  Widget _buildMessage(ChatMessage message) {
    if (message.isUser) return MessageBubble(message: message);

    final reply = message.reply;
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MessageBubble(message: message),
        if (reply != null) ...[
          if (reply.observation != null)
            CurrentConditionsCard(observation: reply.observation!),
          if (reply.forecast.isNotEmpty)
            ForecastStrip(
              days: reply.forecast,
              localeCode: Localizations.localeOf(context).languageCode,
            ),
          for (final alert in reply.alerts) AlertCard(alert: alert),
          if (reply.sourceName != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Text(
                '${l10n.sourceHeader}: ${reply.sourceName}',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
            ),
          if (reply.candidates.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final candidate in reply.candidates)
                    ActionChip(
                      avatar: const Icon(Icons.place_outlined, size: 16),
                      label: Text(
                        [candidate.name, candidate.state]
                            .whereType<String>()
                            .join(', '),
                      ),
                      onPressed: () => _pickCandidate(reply, candidate),
                    ),
                ],
              ),
            ),
          if (reply.suggestions.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final suggestion in reply.suggestions)
                    ActionChip(
                      label: Text(suggestion),
                      onPressed: () => _send(suggestion),
                    ),
                ],
              ),
            ),
        ],
      ],
    );
  }
}

class _Welcome extends StatelessWidget {
  const _Welcome({
    required this.l10n,
    required this.theme,
    required this.onPrompt,
  });

  final AppLocalizations l10n;
  final ThemeData theme;
  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.forum_outlined, size: 56, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              l10n.chatWelcomeTitle,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.chatWelcomeBody,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (final prompt in ChatScreen.starterPrompts)
                  ActionChip(
                    label: Text(prompt),
                    onPressed: () => onPrompt(prompt),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.enabled,
    required this.hint,
    required this.sendTooltip,
    required this.micTooltip,
    required this.listening,
    required this.onSend,
    required this.onMic,
  });

  final TextEditingController controller;
  final bool enabled;
  final String hint;
  final String sendTooltip;
  final String micTooltip;
  final bool listening;
  final ValueChanged<String> onSend;
  final VoidCallback onMic;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                enabled: enabled,
                onSubmitted: onSend,
                textInputAction: TextInputAction.send,
                decoration: InputDecoration(
                  hintText: hint,
                  filled: true,
                  isDense: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(28),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filledTonal(
              onPressed: onMic,
              tooltip: micTooltip,
              icon: Icon(
                listening ? Icons.stop_circle : Icons.mic_none,
                color: listening ? Theme.of(context).colorScheme.error : null,
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: enabled ? () => onSend(controller.text) : null,
              tooltip: sendTooltip,
              icon: const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}