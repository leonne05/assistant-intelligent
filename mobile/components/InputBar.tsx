import { TextInput, View } from 'react-native';
import { IconButton, Text } from 'react-native-paper';

type Props = {
  text: string;
  onChangeText: (text: string) => void;
  isRecording: boolean;
  recordingMillis: number;
  voiceNoteMillis: number | null;
  isThinking: boolean;
  primaryColor: string;
  onPlus: () => void;
  onMicPressIn: () => void;
  onMicPressOut: () => void;
  onPlayVoiceNote: () => void;
  onDeleteVoiceNote: () => void;
  onSend: () => void;
  onStartConversation: () => void;
};

function formatDuration(millis: number) {
  const seconds = Math.floor(millis / 1000);
  return `${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, '0')}`;
}

// La barre du bas : « + » à gauche, le texte au milieu, le micro, puis le gros bouton rond.
export default function InputBar(props: Props) {
  const hasText = props.text.trim() !== '';
  const hasVoiceNote = props.voiceNoteMillis !== null;
  // Le gros bouton rond envoie s'il y a quelque chose à envoyer, sinon il lance la conversation vocale.
  const canSend = hasText || hasVoiceNote;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        minHeight: 58,
        marginHorizontal: 12,
        marginBottom: 8,
        paddingLeft: 4,
        paddingRight: 6,
        borderRadius: 30,
        backgroundColor: '#1E1F26',
      }}
    >
      {props.isRecording ? (
        // Enregistrement en cours (le doigt est sur le micro)
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', paddingLeft: 14 }}>
          <Text variant="bodyLarge" style={{ color: '#F87171' }}>
            ● {formatDuration(props.recordingMillis)}
          </Text>
          <Text variant="bodyMedium" style={{ marginLeft: 12, color: '#8E8C99' }}>
            Relâchez pour terminer
          </Text>
        </View>
      ) : hasVoiceNote ? (
        // Message vocal prêt : supprimer, réécouter
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>
          <IconButton icon="delete" iconColor="#8E8C99" onPress={props.onDeleteVoiceNote} />
          <IconButton icon="play" iconColor="#FFFFFF" onPress={props.onPlayVoiceNote} />
          <Text variant="bodyLarge" style={{ color: '#E8E6F3' }}>
            Message vocal · {formatDuration(props.voiceNoteMillis ?? 0)}
          </Text>
        </View>
      ) : (
        // Saisie normale
        <>
          <IconButton icon="plus" iconColor="#E8E6F3" size={26} onPress={props.onPlus} accessibilityLabel="Ajouter" />
          <TextInput
            placeholder="Demander à JARVIS"
            placeholderTextColor="#8E8C99"
            value={props.text}
            onChangeText={props.onChangeText}
            onSubmitEditing={props.onSend}
            returnKeyType="send"
            style={{ flex: 1, minWidth: 0, color: '#FFFFFF', fontSize: 17, paddingVertical: 10 }}
          />
        </>
      )}

      {/* Le micro : maintenir pour enregistrer un message vocal (caché quand on écrit) */}
      {!hasText && !hasVoiceNote && (
        <IconButton
          icon="microphone-outline"
          iconColor={props.isRecording ? '#F87171' : '#E8E6F3'}
          size={props.isRecording ? 30 : 26}
          disabled={props.isThinking}
          onPressIn={props.onMicPressIn}
          onPressOut={props.onMicPressOut}
          accessibilityLabel="Maintenir pour enregistrer un message vocal"
        />
      )}

      {/* Le gros bouton rond : envoyer, ou parler à JARVIS en mode mains libres */}
      {!props.isRecording && (
        <IconButton
          icon={canSend ? 'arrow-up' : 'waveform'}
          mode="contained"
          containerColor={props.primaryColor}
          iconColor="#FFFFFF"
          size={24}
          disabled={props.isThinking}
          onPress={canSend ? props.onSend : props.onStartConversation}
          style={{ margin: 0 }}
          accessibilityLabel={canSend ? 'Envoyer' : 'Conversation vocale'}
        />
      )}
    </View>
  );
}