import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { useEffect, useRef, useState } from 'react';
import { Modal, View } from 'react-native';
import { IconButton, Text, useTheme } from 'react-native-paper';

// Au-dessus de ce volume (en décibels), on considère que tu parles.
const SPEECH_LEVEL_DB = -40;
// Durée de silence après ta phrase avant que JARVIS considère que tu as fini.
const SILENCE_MILLIS = 1300;
// Si tu ne dis rien pendant ce temps, l'écoute se met en pause.
const NO_SPEECH_TIMEOUT_MILLIS = 12000;

type Phase = 'listening' | 'thinking' | 'speaking' | 'paused';

const LABELS: Record<Phase, string> = {
  listening: 'Je t’écoute…',
  thinking: 'JARVIS réfléchit…',
  speaking: 'JARVIS parle…',
  paused: 'En pause',
};

type Props = {
  visible: boolean;
  onClose: () => void;
  onTranscribe: (uri: string) => Promise<string>;
  onAsk: (text: string, onSpeaking: () => void) => Promise<void>;
  onStopSpeaking: () => void;
};

export default function VoiceMode({ visible, onClose, onTranscribe, onAsk, onStopSpeaking }: Props) {
  const theme = useTheme();
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const recorderState = useAudioRecorderState(recorder, 100);
  const [phase, setPhase] = useState<Phase>('listening');
  const [caption, setCaption] = useState('');

  const isActiveRef = useRef(false);
  const isFinishingRef = useRef(false);
  const hasSpokenRef = useRef(false);
  const silenceStartRef = useRef<number | null>(null);
  const listenStartRef = useRef(0);

  useEffect(() => {
    if (visible) {
      isActiveRef.current = true;
      listen();
    } else {
      isActiveRef.current = false;
      stopRecorder();
      onStopSpeaking();
    }
  }, [visible]);

  async function stopRecorder() {
    if (recorder.isRecording) {
      await recorder.stop();
    }
    // On repasse en mode lecture, sinon l'iPhone joue le son dans l'écouteur du haut, très bas.
    await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
  }

  async function listen() {
    if (!isActiveRef.current) {
      return;
    }
    setPhase('listening');
    isFinishingRef.current = false;
    hasSpokenRef.current = false;
    silenceStartRef.current = null;

    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        pause("J'ai besoin de l'accès au micro. Autorise-le dans les réglages du téléphone.");
        return;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      listenStartRef.current = Date.now();
    } catch (error) {
      pause(`Micro indisponible : ${String(error)}`);
    }
  }

  function pause(message: string) {
    stopRecorder();
    setPhase('paused');
    setCaption(message);
  }

  // Toutes les 100 ms : on regarde le volume du micro pour savoir si tu parles ou si tu as fini.
  useEffect(() => {
    if (phase !== 'listening' || !recorderState.isRecording || isFinishingRef.current) {
      return;
    }
    const now = Date.now();
    const level = recorderState.metering ?? -160;

    if (level > SPEECH_LEVEL_DB) {
      hasSpokenRef.current = true;
      silenceStartRef.current = null;
    } else if (hasSpokenRef.current) {
      if (silenceStartRef.current === null) {
        silenceStartRef.current = now;
      } else if (now - silenceStartRef.current > SILENCE_MILLIS) {
        finishTurn();
      }
    } else if (now - listenStartRef.current > NO_SPEECH_TIMEOUT_MILLIS) {
      pause("Je n'entends rien. Touche le micro pour reprendre.");
    }
  }, [recorderState]);

  async function finishTurn() {
    isFinishingRef.current = true;
    await stopRecorder();
    if (!isActiveRef.current || recorder.uri === null) {
      return;
    }

    try {
      setPhase('thinking');
      setCaption('');
      const text = await onTranscribe(recorder.uri);
      if (!isActiveRef.current) {
        return;
      }
      if (text === '') {
        listen();
        return;
      }
      setCaption(`« ${text} »`);
      await onAsk(text, () => setPhase('speaking'));
      listen();
    } catch (error) {
      pause(error instanceof Error ? error.message : String(error));
    }
  }

  // L'orbe grossit quand tu parles fort, comme dans l'appli Claude.
  const level = recorderState.metering ?? -160;
  const orbSize =
    phase === 'listening' ? 140 + Math.max(0, level + 60) : phase === 'speaking' ? 170 : phase === 'thinking' ? 120 : 110;

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: theme.colors.background }}>
        <View
          style={{
            width: orbSize,
            height: orbSize,
            borderRadius: orbSize / 2,
            backgroundColor: phase === 'paused' ? '#D9D9DE' : theme.colors.primary,
            opacity: phase === 'thinking' ? 0.5 : 1,
          }}
        />
        <Text variant="headlineSmall" style={{ marginTop: 40 }}>
          {LABELS[phase]}
        </Text>
        {caption !== '' && (
          <Text variant="bodyLarge" style={{ marginTop: 12, textAlign: 'center' }}>
            {caption}
          </Text>
        )}

        <View style={{ position: 'absolute', bottom: 56, flexDirection: 'row' }}>
          {phase === 'paused' && (
            <IconButton
              icon="microphone"
              mode="contained"
              containerColor={theme.colors.primary}
              iconColor="#FFFFFF"
              size={32}
              onPress={listen}
            />
          )}
          <IconButton icon="close" mode="contained" size={32} onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}