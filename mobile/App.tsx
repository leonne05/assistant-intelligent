import { AudioPlayer, createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import * as Speech from 'expo-speech';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, View } from 'react-native';
import { ActivityIndicator, IconButton, MD3LightTheme, PaperProvider, Text, TextInput } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import MessageBubble, { Message } from './components/MessageBubble';
import VoiceMode from './components/VoiceMode';

// Adresse du serveur Python : remplace par l'adresse IPv4 de ton PC (commande ipconfig).
const API_URL = 'http://172.20.10.7:8000';

const NETWORK_ERROR = "Je n'arrive pas à joindre mon cerveau. Vérifie que le serveur est lancé et que tu es sur le même Wi-Fi.";

const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#E0479E',
    background: '#FFFFFF',
  },
};

type JarvisReply = {
  reply: string;
  audio: string | null;
};

export default function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [voiceModeOpen, setVoiceModeOpen] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const finishSpeakingRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    // Sur iPhone : JARVIS parle même quand le bouton silencieux est activé.
    setAudioModeAsync({ playsInSilentMode: true });
  }, []);

  function addMessage(role: Message['role'], content: string) {
    const message: Message = { id: Date.now().toString() + role, role, text: content };
    setMessages((previous) => [...previous, message]);
  }

  // ----- Voix de JARVIS -----

  function stopSpeaking() {
    Speech.stop();
    playerRef.current?.remove();
    playerRef.current = null;
    finishSpeakingRef.current?.();
    finishSpeakingRef.current = null;
  }

  async function playAudio(audioBase64: string) {
    // On enregistre le MP3 reçu du serveur dans un fichier temporaire, puis on le joue jusqu'au bout.
    const file = new File(Paths.cache, `jarvis-${Date.now()}.mp3`);
    await file.write(audioBase64, { encoding: 'base64' });
    const player = createAudioPlayer(file.uri);
    playerRef.current = player;

    await new Promise<void>((resolve) => {
      finishSpeakingRef.current = resolve;
      const subscription = player.addListener('playbackStatusUpdate', (status) => {
        if (status.didJustFinish) {
          subscription.remove();
          resolve();
        }
      });
      player.play();
    });
  }

  // La promesse se termine quand JARVIS a fini de parler.
  async function speak(content: string, audioBase64: string | null) {
    stopSpeaking();
    if (audioBase64) {
      try {
        await playAudio(audioBase64);
        return;
      } catch {
        // Voix Mistral illisible : on utilise la voix du téléphone.
      }
    }
    await new Promise<void>((resolve) => {
      finishSpeakingRef.current = resolve;
      Speech.speak(content, { language: 'fr-FR', onDone: resolve, onStopped: resolve, onError: () => resolve() });
    });
  }

  function toggleVoice() {
    if (voiceEnabled) {
      stopSpeaking();
    }
    setVoiceEnabled(!voiceEnabled);
  }

  // ----- Échanges avec le serveur Python -----

  async function requestReply(content: string, withVoice: boolean): Promise<JarvisReply> {
    let response;
    try {
      response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, voice: withVoice }),
      });
    } catch {
      throw new Error(NETWORK_ERROR);
    }
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail ?? 'Une erreur est survenue, réessaie.');
    }
    return { reply: data.reply, audio: data.audio ?? null };
  }

    async function transcribeAudio(uri: string): Promise<string> {
    // On lit l'enregistrement en base64 pour l'envoyer en JSON, comme les messages écrits.
    let audioBase64;
    try {
      audioBase64 = await new File(uri).base64();
    } catch (error) {
      throw new Error(`Lecture de l'enregistrement impossible : ${String(error)}`);
    }

    let response;
    try {
      response = await fetch(`${API_URL}/transcribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio: audioBase64, file_name: 'audio.m4a' }),
      });
    } catch {
      throw new Error(NETWORK_ERROR);
    }
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail ?? "Je n'ai pas réussi à t'entendre, réessaie.");
    }
    return data.text;
  }

  // ----- Conversation écrite -----

  async function send() {
    const content = text.trim();
    if (content === '' || isThinking) {
      return;
    }
    stopSpeaking();
    addMessage('user', content);
    setText('');
    setIsThinking(true);
    try {
      const { reply, audio } = await requestReply(content, voiceEnabled);
      addMessage('jarvis', reply);
      if (voiceEnabled) {
        speak(reply, audio);
      }
    } catch (error) {
      addMessage('jarvis', error instanceof Error ? error.message : String(error));
    } finally {
      setIsThinking(false);
    }
  }

  // ----- Conversation vocale (appelée par VoiceMode à chaque phrase) -----

  async function askInVoiceMode(content: string, onSpeaking: () => void) {
    addMessage('user', `🎤 ${content}`);
    const { reply, audio } = await requestReply(content, true);
    addMessage('jarvis', reply);
    onSpeaking();
    await speak(reply, audio);
  }

  function onMainButtonPress() {
    if (text.trim() !== '') {
      send();
    } else {
      stopSpeaking();
      setVoiceModeOpen(true);
    }
  }

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
            <View style={{ flexDirection: 'row', justifyContent: 'flex-end' }}>
              <IconButton icon={voiceEnabled ? 'volume-high' : 'volume-off'} onPress={toggleVoice} />
            </View>

            {messages.length === 0 ? (
              <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                <Text variant="displayMedium" style={{ color: theme.colors.primary }}>
                  JARVIS
                </Text>
                <Text variant="titleMedium">Bonjour, que puis-je faire pour toi ?</Text>
              </View>
            ) : (
              <FlatList
                ref={listRef}
                data={messages}
                keyExtractor={(message) => message.id}
                renderItem={({ item }) => <MessageBubble message={item} />}
                contentContainerStyle={{ padding: 12 }}
                onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
              />
            )}

            {isThinking && (
              <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16 }}>
                <ActivityIndicator size="small" />
                <Text variant="bodyMedium" style={{ marginLeft: 8 }}>
                  JARVIS réfléchit…
                </Text>
              </View>
            )}

            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 8 }}>
              <TextInput
                mode="outlined"
                placeholder="Écris à JARVIS…"
                value={text}
                onChangeText={setText}
                onSubmitEditing={send}
                style={{ flex: 1 }}
              />
              <IconButton
                icon={text.trim() !== '' ? 'send' : 'waveform'}
                mode="contained"
                containerColor={theme.colors.primary}
                iconColor="#FFFFFF"
                size={28}
                disabled={isThinking}
                onPress={onMainButtonPress}
              />
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>

        <VoiceMode
          visible={voiceModeOpen}
          onClose={() => setVoiceModeOpen(false)}
          onTranscribe={transcribeAudio}
          onAsk={askInVoiceMode}
          onStopSpeaking={stopSpeaking}
        />
        <StatusBar style="dark" />
      </PaperProvider>
    </SafeAreaProvider>
  );
}