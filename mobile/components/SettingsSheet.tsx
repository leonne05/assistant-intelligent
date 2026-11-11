import { Modal, View } from 'react-native';
import { IconButton, List, Switch, Text, useTheme } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import JarvisBackground from './JarvisBackground';

type Props = {
  visible: boolean;
  voiceEnabled: boolean;
  serverUrl: string;
  onToggleVoice: () => void;
  onClose: () => void;
};

// Les réglages, ouverts avec le bouton en haut à droite.
export default function SettingsSheet({ visible, voiceEnabled, serverUrl, onToggleVoice, onClose }: Props) {
  const theme = useTheme();

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
          <JarvisBackground />
          <SafeAreaView style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12 }}>
              <IconButton icon="chevron-down" mode="contained" containerColor="#151821" iconColor="#FFFFFF" onPress={onClose} />
              <Text variant="titleMedium" style={{ marginLeft: 8, color: '#E8E6F3' }}>
                Réglages
              </Text>
            </View>

            <List.Section>
              <List.Item
                title="Réponses à voix haute"
                description="Dans la conversation écrite"
                left={(props) => <List.Icon {...props} icon="volume-high" />}
                right={() => <Switch value={voiceEnabled} onValueChange={onToggleVoice} />}
              />
              <List.Item
                title="Serveur JARVIS"
                description={serverUrl === '' ? 'Non configuré (fichier mobile/.env)' : serverUrl}
                left={(props) => <List.Icon {...props} icon="server" />}
              />
            </List.Section>
          </SafeAreaView>
        </View>
      </SafeAreaProvider>
    </Modal>
  );
}