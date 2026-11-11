import { Pressable, ScrollView, TextInput, useWindowDimensions, View } from 'react-native';
import { IconButton, Text } from 'react-native-paper';
import { SharedValue } from 'react-native-reanimated';
import JarvisOrb, { OrbPhase } from './JarvisOrb';

type Props = {
  phase: OrbPhase;
  level: SharedValue<number>;
  reply: string | null;
  status: string;
  muted: boolean;
  text: string;
  primaryColor: string;
  onChangeText: (text: string) => void;
  onFocusText: () => void;
  onBlurText: () => void;
  onSend: () => void;
  onPlus: () => void;
  onOrbPress: () => void;
  onToggleMute: () => void;
  onClose: () => void;
  onOpenSettings: () => void;
};

// L'écran de conversation vocale : l'orbe, la dernière réponse de JARVIS et les boutons du bas.
export default function VoiceScreen(props: Props) {
  const { width } = useWindowDimensions();
  const hasText = props.text.trim() !== '';

  return (
    <View style={{ flex: 1 }}>
      {/* En-tête : revenir à la conversation à gauche, réglages à droite */}
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 12 }}>
        <IconButton
          icon="chevron-down"
          mode="contained"
          containerColor="#1E1F26"
          iconColor="#FFFFFF"
          onPress={props.onClose}
          accessibilityLabel="Revenir à la conversation"
        />
        <IconButton
          icon="tune-variant"
          mode="contained"
          containerColor="#1E1F26"
          iconColor="#FFFFFF"
          onPress={props.onOpenSettings}
          accessibilityLabel="Réglages"
        />
      </View>

      {props.reply === null ? (
        // Pas encore de réponse : grand orbe au centre
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Pressable onPress={props.onOrbPress} accessibilityLabel="Orbe de JARVIS">
            <JarvisOrb size={width * 0.8} phase={props.phase} level={props.level} />
          </Pressable>
          <Text variant="bodyLarge" style={{ color: '#A9A6C2', minHeight: 24 }}>
            {props.status}
          </Text>
        </View>
      ) : (
        // Une réponse : le texte en haut, le petit orbe en bas
        <>
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 24, paddingTop: 16 }}>
            <Text style={{ color: '#FFFFFF', fontSize: 20, lineHeight: 30 }}>{props.reply}</Text>
          </ScrollView>
          <View style={{ alignItems: 'center', paddingVertical: 8 }}>
            <Pressable onPress={props.onOrbPress} accessibilityLabel="Orbe de JARVIS">
              <JarvisOrb size={120} phase={props.phase} level={props.level} />
            </Pressable>
            <Text variant="bodyMedium" style={{ color: '#A9A6C2', minHeight: 22 }}>
              {props.status}
            </Text>
          </View>
        </>
      )}

      {/* Les boutons du bas : écrire, couper le micro, terminer */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingBottom: 8 }}>
        <View
          style={{
            flex: 1,
            flexDirection: 'row',
            alignItems: 'center',
            minHeight: 52,
            paddingRight: 4,
            borderRadius: 26,
            backgroundColor: '#1E1F26',
          }}
        >
          <IconButton icon="plus" iconColor="#E8E6F3" onPress={props.onPlus} accessibilityLabel="Ajouter" />
          <TextInput
            placeholder="Demander à JARVIS"
            placeholderTextColor="#8E8C99"
            value={props.text}
            onChangeText={props.onChangeText}
            onFocus={props.onFocusText}
            onBlur={props.onBlurText}
            onSubmitEditing={props.onSend}
            returnKeyType="send"
            style={{ flex: 1, minWidth: 0, color: '#FFFFFF', fontSize: 17, paddingVertical: 10 }}
          />
          {hasText && (
            <IconButton
              icon="arrow-up"
              mode="contained"
              containerColor={props.primaryColor}
              iconColor="#FFFFFF"
              size={20}
              onPress={props.onSend}
              accessibilityLabel="Envoyer"
            />
          )}
        </View>

        {!hasText && (
          <>
            <IconButton
              icon={props.muted ? 'microphone-off' : 'microphone'}
              mode="contained"
              containerColor={props.muted ? '#DC2626' : '#1E1F26'}
              iconColor="#FFFFFF"
              size={26}
              onPress={props.onToggleMute}
              accessibilityLabel={props.muted ? 'Réactiver le micro' : 'Couper le micro'}
            />
            <IconButton
              icon="close"
              mode="contained"
              containerColor="#E8E6F3"
              iconColor="#0A0C12"
              size={26}
              onPress={props.onClose}
              style={{ marginLeft: 0 }}
              accessibilityLabel="Terminer la conversation vocale"
            />
          </>
        )}
      </View>
    </View>
  );
}