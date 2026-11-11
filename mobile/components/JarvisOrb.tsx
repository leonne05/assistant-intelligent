import { BlurMask, Canvas, Circle, Fill, Group, RadialGradient, Skia, SweepGradient, useClock, vec } from '@shopify/react-native-skia';
import { SharedValue, useDerivedValue } from 'react-native-reanimated';

export type OrbPhase = 'idle' | 'listening' | 'thinking' | 'speaking';

type Props = {
  size: number;
  phase: OrbPhase;
  // Volume de ta voix entre 0 et 1 (pendant l'écoute), pour que l'orbe réagisse.
  level: SharedValue<number>;
};

// Les couleurs irisées qui tournent sur le bord de l'orbe.
const IRIDESCENT_COLORS = ['#F27BBD', '#F8B98C', '#F6E3A8', '#9FF0D2', '#7FD3F5', '#7C9CF5', '#A374F7', '#E08AF0', '#F27BBD'];

export default function JarvisOrb({ size, phase, level }: Props) {
  const clock = useClock();
  const center = size / 2;
  // L'orbe occupe le centre du dessin ; la marge autour laisse la place au halo.
  const baseRadius = size * 0.38;

  // Taille de l'orbe : elle respire doucement, grossit quand tu parles et pulse quand JARVIS parle.
  const radius = useDerivedValue(() => {
    const t = clock.value / 1000;
    if (phase === 'listening') {
      return baseRadius * (1 + 0.02 * Math.sin(t * 2) + 0.12 * level.value);
    }
    if (phase === 'speaking') {
      return baseRadius * (1.03 + 0.035 * Math.sin(t * 7) * Math.sin(t * 2.3));
    }
    if (phase === 'thinking') {
      return baseRadius * (0.96 + 0.02 * Math.sin(t * 3));
    }
    return baseRadius * (1 + 0.015 * Math.sin(t * 1.5));
  });

  // Contour légèrement déformé, comme une bulle vivante.
  const outline = useDerivedValue(() => {
    const t = clock.value / 1000;
    const wobble = phase === 'listening' ? 0.012 + 0.035 * level.value : phase === 'speaking' ? 0.018 : 0.01;
    const builder = Skia.PathBuilder.Make();
    const points = 96;
    for (let i = 0; i <= points; i++) {
      const angle = (i / points) * Math.PI * 2;
      const r = radius.value * (1 + wobble * Math.sin(3 * angle + t * 1.3) + wobble * 0.6 * Math.sin(2 * angle - t * 0.9));
      const x = center + r * Math.cos(angle);
      const y = center + r * Math.sin(angle);
      if (i === 0) {
        builder.moveTo(x, y);
      } else {
        builder.lineTo(x, y);
      }
    }
    builder.close();
    return builder.build();
  });

  // Les reflets irisés tournent, plus vite quand JARVIS réfléchit.
  const rotation = useDerivedValue(() => {
    const speed = phase === 'thinking' ? 1.6 : phase === 'speaking' ? 0.8 : 0.35;
    return [{ rotate: (clock.value / 1000) * speed }];
  });

  const glowRadius = useDerivedValue(() => radius.value * 1.04);
  const origin = vec(center, center);

  return (
    <Canvas style={{ width: size, height: size }}>
      {/* Halo violet autour de l'orbe */}
      <Circle cx={center} cy={center} r={glowRadius} color="rgba(130, 90, 255, 0.3)">
        <BlurMask blur={size * 0.04} style="normal" />
      </Circle>

      <Group clip={outline}>
        {/* 1. Les couleurs irisées qui tournent (floutées pour des transitions douces) */}
        <Group transform={rotation} origin={origin}>
          <Circle cx={center} cy={center} r={size / 2}>
            <SweepGradient c={origin} colors={IRIDESCENT_COLORS} />
            <BlurMask blur={size * 0.05} style="normal" />
          </Circle>
        </Group>

        {/* 2. Le cœur violet, décalé, qui laisse les reflets sur le bord */}
        <Fill>
          <RadialGradient
            c={vec(center + size * 0.035, center + size * 0.03)}
            r={size * 0.36}
            colors={['#9B6CF6', 'rgba(155, 108, 246, 0.88)', 'rgba(155, 108, 246, 0)']}
            positions={[0, 0.45, 1]}
          />
        </Fill>

        {/* 3. Le point de lumière en haut à gauche */}
        <Fill>
          <RadialGradient
            c={vec(center - size * 0.11, center - size * 0.13)}
            r={size * 0.26}
            colors={['rgba(248, 240, 255, 0.85)', 'rgba(230, 215, 255, 0.3)', 'rgba(255, 255, 255, 0)']}
            positions={[0, 0.45, 1]}
          />
        </Fill>
      </Group>
    </Canvas>
  );
}