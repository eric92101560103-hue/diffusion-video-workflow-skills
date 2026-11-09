// Insert this sequence into the current scene above the picture track.
// Each group's children and keyframes use that group's local time.
// This card plays for 3 seconds at the editor's documented 30 fps frame clock.
export default function ExplainerCards() {
  return (
    <sequence id="explainer-cards" name="輔助標題小卡">
      <group id="explainer-card-example" name="現場有了新線索" x={76} y={108} start={8} end={11}>
        <rect id="explainer-card-example-panel" name="小卡底色" width={520} height={132} end={3} cornerRadius={24} fill="#10201F" opacity={0.88} />
        <rect id="explainer-card-example-accent" name="綠色標記" x={22} y={23} width={5} height={86} end={3} cornerRadius={2.5} fill="#75E6B1" />
        <text id="explainer-card-example-label" name="小標" x={44} y={19} width={454} height={33} end={3} fontFamily="Noto Sans TC" fontSize={26} fontWeight={500} color="#A6EAC9" textBaseline="middle">轉折</text>
        <text id="explainer-card-example-title" name="主標" x={42} y={54} width={454} height={58} end={3} fontFamily="Noto Sans TC" fontSize={45} fontWeight={700} color="#F5FAF8" textBaseline="middle">現場有了新線索</text>
        <keyframeTrack property="opacity">
          <keyframe time="0f" value={0} />
          <keyframe time="6f" value={1} easing="cubicBezier(0.23,1,0.32,1)" />
          <keyframe time="84f" value={1} />
          <keyframe time="89f" value={0} easing="cubicBezier(0.23,1,0.32,1)" />
        </keyframeTrack>
        <keyframeTrack property="offsetY">
          <keyframe time="0f" value={12} />
          <keyframe time="6f" value={0} easing="cubicBezier(0.23,1,0.32,1)" />
          <keyframe time="84f" value={0} />
          <keyframe time="89f" value={12} easing="cubicBezier(0.23,1,0.32,1)" />
        </keyframeTrack>
      </group>
    </sequence>
  );
}
