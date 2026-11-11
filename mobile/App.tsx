import {
  AudioPlayer,
  createAudioPlayer,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import * as Speech from 'expo-speech';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { AppState, FlatList, Keyboard, KeyboardAvoidingView, Pressable, View } from 'react-native';
import { ActivityIndicator, IconButton, MD3DarkTheme, PaperProvider, Text } from 'react-native-paper';
import { useSharedValue, withTiming } from 'react-native-reanimated';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import InputBar from './components/InputBar';
import JarvisBackground from './components/JarvisBackground';
import JarvisOrb, { OrbPhase } from './components/JarvisOrb';
import MessageBubble, { Message } from './components/MessageBubble';
import SettingsSheet from './components/SettingsSheet';
import VoiceScreen from './components/VoiceScreen';

// Adresse du serveur Python : remplace par l'adresse IPv4 de ton PC (commande ipconfig).
const API_URL = 'http://172.20.10.7:8000';

// En dessous de cette durée, on considère que c'était un simple appui, pas un message vocal.
const MIN_VOICE_NOTE_MILLIS = 700;

// Mode vocal : au-dessus de ce volume (en décibels), on considère que tu parles.
const SPEECH_LEVEL_DB = -40;
// Durée de silence après ta phrase avant que JARVIS considère que tu as fini.
const SILENCE_MILLIS = 1300;
// Si personne ne parle pendant ce temps, on recommence un enregistrement neuf (pour ne pas garder un long fichier vide).
const RESTART_LISTENING_MILLIS = 15000;

const NETWORK_ERROR =
  "Je n'arrive pas à joindre mon cerveau. Vérifiez que le serveur est lancé et que vous êtes sur le même Wi-Fi.";

const theme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#A374F7',
    background: '#0A0C12',
  },
};

type VoiceNote = {
  uri: string;
  durationMillis: number;
};

export default function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [hint, setHint] = useState('');
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [voiceNote, setVoiceNote] = useState<VoiceNote | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Écran de conversation vocale
  const [handsFree, setHandsFree] = useState(false);
  const [handsFreeListening, setHandsFreeListening] = useState(false);
  const [voiceReply, setVoiceReply] = useState<string | null>(null);
  const [voiceText, setVoiceText] = useState('');
  const [muted, setMuted] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const finishSpeakingRef = useRef<(() => void) | null>(null);
  const isPressingRef = useRef(false);
  // Mode vocal (des « ref » car ces valeurs doivent être à jour tout de suite, pas au prochain affichage)
  const handsFreeRef = useRef(false);
  const mutedRef = useRef(false);
  const voiceBusyRef = useRef(false);
  const isFinishingRef = useRef(false);
  const hasSpokenRef = useRef(false);
  const silenceStartRef = useRef<number | null>(null);
  const listenStartRef = useRef(0);
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const recorderState = useAudioRecorderState(recorder, 100);
  const level = useSharedValue(0);

  useEffect(() => {
    // Sur iPhone : JARVIS parle même quand le bouton silencieux est activé.
    setAudioModeAsync({ playsInSilentMode: true });
  }, []);

  // Toutes les 100 ms : l'orbe suit le volume de ta voix, et en mode vocal on détecte la fin de ta phrase.
  useEffect(() => {
    const decibels = recorderState.isRecording ? (recorderState.metering ?? -160) : -160;
    level.value = withTiming(Math.min(1, Math.max(0, (decibels + 60) / 45)), { duration: 100 });

    if (!handsFreeRef.current || !handsFreeListening || !recorderState.isRecording || isFinishingRef.current) {
      return;
    }
    const now = Date.now();
    if (decibels > SPEECH_LEVEL_DB) {
      hasSpokenRef.current = true;
      silenceStartRef.current = null;
    } else if (hasSpokenRef.current) {
      if (silenceStartRef.current === null) {
        silenceStartRef.current = now;
      } else if (now - silenceStartRef.current > SILENCE_MILLIS) {
        finishHandsFreeTurn();
      }
    } else if (now - listenStartRef.current > RESTART_LISTENING_MILLIS) {
      restartHandsFreeListening();
    }
  }, [recorderState]);

  // Appli en arrière-plan : on quitte le mode vocal (le micro ne peut pas rester ouvert).
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state !== 'active') {
        stopHandsFree();
      }
    });
    return () => subscription.remove();
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
    setIsSpeaking(false);
    finishSpeakingRef.current?.();
    finishSpeakingRef.current = null;
  }

  // Joue un fichier son ; la promesse se termine quand la lecture est finie.
  function play(source: string) {
    stopSpeaking();
    const player = createAudioPlayer(source);
    playerRef.current = player;
    return new Promise<void>((resolve) => {
      finishSpeakingRef.current = resolve;
      const subscription = player.addListener('playbackStatusUpdate', (status) => {
        if (status.didJustFinish) {
          subscription.remove();
          setIsSpeaking(false);
          resolve();
        }
      });
      player.play();
    });
  }

  // JARVIS parle (voix Mistral, ou voix du téléphone en secours) ; la promesse se termine quand il a fini.
  async function speak(content: string, audioBase64: string | null) {
    stopSpeaking();
    setIsSpeaking(true);
    if (audioBase64) {
      try {
        // On enregistre le MP3 reçu du serveur dans un fichier temporaire, puis on le joue.
        const file = new File(Paths.cache, `jarvis-${Date.now()}.mp3`);
        await file.write(audioBase64, { encoding: 'base64' });
        setIsSpeaking(true);
        await play(file.uri);
        return;
      } catch {
        // Voix Mistral illisible : on utilise la voix du téléphone.
      }
    }
    setIsSpeaking(true);
    await new Promise<void>((resolve) => {
      finishSpeakingRef.current = resolve;
      const done = () => {
        setIsSpeaking(false);
        resolve();
      };
      Speech.speak(content, { language: 'fr-FR', onDone: done, onStopped: done, onError: done });
    });
  }

  function jarvisSays(content: string, audioBase64?: string | null) {
    addMessage('jarvis', content);
    if (voiceEnabled) {
      speak(content, audioBase64 ?? null);
    }
  }

  // ----- Échanges avec le serveur Python -----

  async function requestReply(content: string, withVoice: boolean) {
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
      throw new Error(data.detail ?? 'Une erreur est survenue, réessayez.');
    }
    return {
      reply: data.reply as string,
      audio: (data.audio ?? null) as string | null,
    };
  }

  async function transcribeAudio(uri: string) {
    // On lit l'enregistrement en base64 pour l'envoyer en JSON, comme les messages écrits.
    const audioBase64 = await new File(uri).base64();

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
    const rawText = await response.text();
    let data;
    try {
      data = JSON.parse(rawText);
    } catch {
      throw new Error(`Le serveur a répondu ${response.status} : ${rawText.slice(0, 120)}`);
    }
    if (!response.ok) {
      throw new Error(data.detail ?? "Je n'ai pas réussi à vous entendre, réessayez.");
    }
    return data.text as string;
  }

  async function askJarvis(content: string) {
    setIsThinking(true);
    try {
      const { reply, audio } = await requestReply(content, voiceEnabled);
      jarvisSays(reply, audio);
    } catch (error) {
      jarvisSays(error instanceof Error ? error.message : String(error));
    } finally {
      setIsThinking(false);
    }
  }

  // ----- Écran vocal : JARVIS écoute, répond, puis réécoute tout seul -----

  async function stopRecorder() {
    if (recorder.isRecording) {
      await recorder.stop();
    }
    // On repasse en mode lecture, sinon l'iPhone joue le son dans l'écouteur du haut, très bas.
    await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
  }

  function startHandsFree() {
    if (isThinking || recorderState.isRecording || voiceNote !== null) {
      return;
    }
    Keyboard.dismiss();
    stopSpeaking();
    setHint('');
    handsFreeRef.current = true;
    mutedRef.current = false;
    voiceBusyRef.current = false;
    setMuted(false);
    setVoiceReply(null);
    setVoiceText('');
    setHandsFree(true);
    listenHandsFree();
  }

  // On quitte l'écran vocal et on revient à la conversation (avec un message d'erreur éventuel).
  function stopHandsFree(errorMessage?: string) {
    if (!handsFreeRef.current) {
      return;
    }
    handsFreeRef.current = false;
    setHandsFree(false);
    setHandsFreeListening(false);
    stopRecorder();
    stopSpeaking();
    if (errorMessage) {
      addMessage('jarvis', errorMessage);
    }
  }

  async function listenHandsFree() {
    // On n'écoute pas si le micro est coupé, ou si JARVIS est en train de réfléchir ou de parler.
    if (!handsFreeRef.current || mutedRef.current || voiceBusyRef.current || recorder.isRecording) {
      return;
    }
    isFinishingRef.current = false;
    hasSpokenRef.current = false;
    silenceStartRef.current = null;

    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        stopHandsFree("J'ai besoin de l'accès au micro. Autorisez-le dans les réglages du téléphone.");
        return;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      listenStartRef.current = Date.now();
      setHandsFreeListening(true);
    } catch (error) {
      stopHandsFree(`Micro indisponible : ${String(error)}`);
    }
  }

  // On arrête d'écouter sans quitter l'écran vocal (micro coupé, ou on écrit au clavier).
  async function pauseListening() {
    isFinishingRef.current = true;
    setHandsFreeListening(false);
    await stopRecorder();
  }

  async function restartHandsFreeListening() {
    await pauseListening();
    listenHandsFree();
  }

  async function finishHandsFreeTurn() {
    await pauseListening();
    if (!handsFreeRef.current || recorder.uri === null) {
      return;
    }

    voiceBusyRef.current = true;
    setIsThinking(true);
    let transcription;
    try {
      transcription = await transcribeAudio(recorder.uri);
    } catch (error) {
      voiceBusyRef.current = false;
      setIsThinking(false);
      stopHandsFree(error instanceof Error ? error.message : String(error));
      return;
    }
    if (transcription === '') {
      voiceBusyRef.current = false;
      setIsThinking(false);
      listenHandsFree();
      return;
    }
    await answerInVoiceMode(transcription, `🎤 ${transcription}`);
  }

  // JARVIS répond à voix haute sur l'écran vocal, puis réécoute.
  async function answerInVoiceMode(content: string, shownText: string) {
    voiceBusyRef.current = true;
    addMessage('user', shownText);
    setIsThinking(true);
    try {
      const { reply, audio } = await requestReply(content, true);
      if (!handsFreeRef.current) {
        return;
      }
      setIsThinking(false);
      addMessage('jarvis', reply);
      setVoiceReply(reply);
      // On attend que JARVIS ait fini de parler avant de réécouter, sinon il s'entendrait lui-même.
      await speak(reply, audio);
    } catch (error) {
      stopHandsFree(error instanceof Error ? error.message : String(error));
      return;
    } finally {
      setIsThinking(false);
      voiceBusyRef.current = false;
    }
    listenHandsFree();
  }

  function toggleMute() {
    if (mutedRef.current) {
      mutedRef.current = false;
      setMuted(false);
      listenHandsFree();
    } else {
      mutedRef.current = true;
      setMuted(true);
      pauseListening();
    }
  }

  // Sur l'écran vocal, on peut aussi écrire : on arrête d'écouter pendant qu'on tape.
  function onVoiceTextFocus() {
    pauseListening();
  }

  function onVoiceTextBlur() {
    if (voiceText.trim() === '') {
      listenHandsFree();
    }
  }

  async function sendVoiceText() {
    const content = voiceText.trim();
    if (content === '' || voiceBusyRef.current) {
      return;
    }
    setVoiceText('');
    Keyboard.dismiss();
    stopSpeaking();
    await pauseListening();
    answerInVoiceMode(content, content);
  }

  // Toucher l'orbe pendant que JARVIS parle l'interrompt (il se remet à écouter).
  function onVoiceOrbPress() {
    if (isSpeaking) {
      stopSpeaking();
    }
  }

  // ----- Conversation écrite (page d'accueil) -----

  function sendText(content: string) {
    if (content === '' || isThinking) {
      return;
    }
    stopSpeaking();
    setHint('');
    addMessage('user', content);
    askJarvis(content);
  }

  function send() {
    sendText(text.trim());
    setText('');
  }

  // ----- Message vocal, comme sur WhatsApp : maintenir pour enregistrer, relâcher, puis envoyer -----

  async function startRecording() {
    if (text.trim() !== '' || voiceNote !== null || isThinking || handsFreeRef.current) {
      return;
    }
    isPressingRef.current = true;

    const permission = await requestRecordingPermissionsAsync();
    if (!permission.granted) {
      isPressingRef.current = false;
      setHint("J'ai besoin de l'accès au micro. Autorisez-le dans les réglages du téléphone.");
      return;
    }

    stopSpeaking();
    setHint('');
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();

    // Le doigt a été levé pendant la préparation du micro : on arrête tout de suite.
    if (!isPressingRef.current) {
      await finishRecording();
    }
  }

  async function finishRecording() {
    isPressingRef.current = false;
    if (!recorder.isRecording || handsFreeRef.current) {
      return;
    }

    const durationMillis = recorder.getStatus().durationMillis;
    await recorder.stop();
    // On repasse en mode lecture, sinon l'iPhone joue le son dans l'écouteur du haut, très bas.
    await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });

    if (recorder.uri === null || durationMillis < MIN_VOICE_NOTE_MILLIS) {
      setHint('Maintenez le micro appuyé pendant que vous parlez.');
      return;
    }
    setVoiceNote({ uri: recorder.uri, durationMillis });
  }

  async function sendVoiceNote() {
    if (voiceNote === null) {
      return;
    }
    const { uri } = voiceNote;
    setVoiceNote(null);
    stopSpeaking();
    setIsThinking(true);

    try {
      const transcription = await transcribeAudio(uri);
      if (transcription === '') {
        jarvisSays("Je n'ai rien entendu, réessayez.");
        return;
      }
      addMessage('user', `🎤 ${transcription}`);
      await askJarvis(transcription);
    } catch (error) {
      jarvisSays(error instanceof Error ? error.message : String(error));
    } finally {
      setIsThinking(false);
    }
  }

  function deleteVoiceNote() {
    stopSpeaking();
    setVoiceNote(null);
  }

  function onMainButtonPress() {
    if (voiceNote !== null) {
      sendVoiceNote();
    } else if (text.trim() !== '') {
      send();
    }
  }

  const isRecording = recorderState.isRecording;
  const orbPhase: OrbPhase = isRecording ? 'listening' : isThinking ? 'thinking' : isSpeaking ? 'speaking' : 'idle';
  const voiceStatus = muted
    ? 'Micro coupé'
    : isThinking
      ? 'Réflexion en cours…'
      : handsFreeListening
        ? 'Je vous écoute…'
        : '';

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <JarvisBackground />
          <SafeAreaView style={{ flex: 1 }}>
            <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
              {handsFree ? (
                // ----- Écran vocal -----
                <VoiceScreen
                  phase={orbPhase}
                  level={level}
                  reply={voiceReply}
                  status={voiceStatus}
                  muted={muted}
                  text={voiceText}
                  primaryColor={theme.colors.primary}
                  onChangeText={setVoiceText}
                  onFocusText={onVoiceTextFocus}
                  onBlurText={onVoiceTextBlur}
                  onSend={sendVoiceText}
                  onPlus={() => {}}
                  onOrbPress={onVoiceOrbPress}
                  onToggleMute={toggleMute}
                  onClose={() => stopHandsFree()}
                  onOpenSettings={() => {
                    stopHandsFree();
                    setSettingsOpen(true);
                  }}
                />
              ) : (
                // ----- Page d'accueil : la conversation -----
                <>
                  <View
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingLeft: 20,
                      paddingRight: 12,
                    }}
                  >
                    <Text variant="titleLarge" style={{ color: '#FFFFFF', fontWeight: '600' }}>
                      JARVIS
                    </Text>
                    <IconButton
                      icon="tune-variant"
                      mode="contained"
                      containerColor="#1E1F26"
                      iconColor="#FFFFFF"
                      onPress={() => setSettingsOpen(true)}
                      accessibilityLabel="Réglages"
                    />
                  </View>

                  {messages.length === 0 ? (
                    // Conversation vide : un petit orbe et une phrase d'accueil
                    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
                      <Pressable onPress={startHandsFree} accessibilityLabel="Parler à JARVIS">
                        <JarvisOrb size={140} phase={orbPhase} level={level} />
                      </Pressable>
                      <Text variant="titleMedium" style={{ color: '#E8E6F3', textAlign: 'center', marginTop: 16 }}>
                        Bonjour, que puis-je faire pour vous ?
                      </Text>
                    </View>
                  ) : (
                    <FlatList
                      ref={listRef}
                      data={messages}
                      keyExtractor={(message) => message.id}
                      renderItem={({ item }) => <MessageBubble message={item} />}
                      contentContainerStyle={{ padding: 12 }}
                      onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
                      keyboardDismissMode="interactive"
                    />
                  )}

                  {isThinking && (
                    <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingBottom: 8 }}>
                      <ActivityIndicator size="small" />
                      <Text variant="bodyMedium" style={{ marginLeft: 8, color: '#A9A6C2' }}>
                        JARVIS réfléchit…
                      </Text>
                    </View>
                  )}
                  {hint !== '' && (
                    <Text
                      variant="bodyMedium"
                      style={{ color: '#A9A6C2', textAlign: 'center', paddingHorizontal: 24, paddingBottom: 8 }}
                    >
                      {hint}
                    </Text>
                  )}

                  <InputBar
                    text={text}
                    onChangeText={setText}
                    isRecording={isRecording}
                    recordingMillis={recorderState.durationMillis}
                    voiceNoteMillis={voiceNote?.durationMillis ?? null}
                    isThinking={isThinking}
                    primaryColor={theme.colors.primary}
                    onPlus={() => setHint('Bientôt : joindre une photo ou un document.')}
                    onMicPressIn={startRecording}
                    onMicPressOut={finishRecording}
                    onPlayVoiceNote={() => voiceNote && play(voiceNote.uri)}
                    onDeleteVoiceNote={deleteVoiceNote}
                    onSend={onMainButtonPress}
                    onStartConversation={startHandsFree}
                  />
                </>
              )}
            </KeyboardAvoidingView>
          </SafeAreaView>
        </View>

        <SettingsSheet
          visible={settingsOpen}
          voiceEnabled={voiceEnabled}
          serverUrl={API_URL}
          onToggleVoice={() => setVoiceEnabled(!voiceEnabled)}
          onClose={() => setSettingsOpen(false)}
        />
        <StatusBar style="light" />
      </PaperProvider>
    </SafeAreaProvider>
  );
}