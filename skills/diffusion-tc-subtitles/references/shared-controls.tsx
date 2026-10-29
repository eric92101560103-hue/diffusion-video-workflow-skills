// Copy these declarations and this component into the composition file.
// @inspect controls must stay in the same file as their JSX consumers.
/** @inspect font path="繁體字幕/文字/字型" */
const subtitleFont = "Noto Sans TC";
/** @inspect number min=12 max=240 step=1 path="繁體字幕/文字/字級" */
const subtitleSize = 80;
/** @inspect number min=100 max=900 step=100 path="繁體字幕/文字/字重" */
const subtitleWeight = 500;
/** @inspect select options="normal,italic,oblique" path="繁體字幕/文字/字體樣式" */
const subtitleFontStyle = "normal";
/** @inspect color path="繁體字幕/文字/文字顏色" */
const subtitleColor = "#FFFFFF";
/** @inspect number min=0.5 max=3 step=0.05 path="繁體字幕/文字/行距倍率" */
const subtitleLeading = 0.9;
/** @inspect number min=-20 max=50 step=0.5 path="繁體字幕/文字/字距" */
const subtitleLetterSpacing = 0.5;
/** @inspect select options="original,upper,lower" path="繁體字幕/文字/英文大小寫" */
const subtitleTextCase = "original";
/** @inspect select options="left,center,right" path="繁體字幕/排版/文字水平對齊" */
const subtitleAlign = "center";
/** @inspect select options="top,middle,bottom,alphabetic" path="繁體字幕/排版/文字垂直對齊" */
const subtitleBaseline = "bottom";
/** @inspect boolean path="繁體字幕/排版/方格水平置中" */
const subtitleCentered = true;
/** @inspect number min=-1440 max=2880 step=0.5 path="繁體字幕/排版/X（關閉置中時）" */
const subtitleLeft = 203.5;
/** @inspect number min=-2560 max=5120 step=1 path="繁體字幕/排版/Y" */
const subtitleTop = 1887;
/** @inspect number min=1 max=2880 step=1 path="繁體字幕/排版/方格寬度" */
const subtitleWidth = 1033;
/** @inspect number min=1 max=2560 step=1 path="繁體字幕/排版/方格高度" */
const subtitleHeight = 91;
/** @inspect boolean path="繁體字幕/排版/鎖定方格比例" */
const subtitleKeepAspect = false;
/** @inspect number min=-180 max=180 step=1 path="繁體字幕/變形/旋轉角度" */
const subtitleRotation = 0;
/** @inspect number min=0.1 max=3 step=0.05 path="繁體字幕/變形/水平縮放" */
const subtitleScaleX = 1;
/** @inspect number min=0.1 max=3 step=0.05 path="繁體字幕/變形/垂直縮放" */
const subtitleScaleY = 1;
/** @inspect number min=-1440 max=1440 step=1 path="繁體字幕/變形/水平偏移" */
const subtitleOffsetX = 0;
/** @inspect number min=-2560 max=2560 step=1 path="繁體字幕/變形/垂直偏移" */
const subtitleOffsetY = 0;
/** @inspect number min=0 max=100 step=1 path="繁體字幕/外觀/不透明度（%）" */
const subtitleOpacity = 90;
/** @inspect select options="sourceOver,multiply,screen,overlay,darken,lighten,colorDodge,colorBurn,hardLight,softLight,difference,exclusion,hue,saturation,color,luminosity" path="繁體字幕/外觀/混合模式" */
const subtitleBlendMode = "sourceOver";
/** @inspect boolean path="繁體字幕/外觀/顯示字幕" */
const subtitleVisible = true;
/** @inspect boolean path="繁體字幕/描邊/啟用描邊" */
const subtitleStrokeEnabled = false;
/** @inspect color path="繁體字幕/描邊/顏色" */
const subtitleStrokeColor = "#000000";
/** @inspect number min=0 max=30 step=0.5 path="繁體字幕/描邊/寬度" */
const subtitleOutline = 6;
/** @inspect number min=0 max=100 step=1 path="繁體字幕/描邊/不透明度（%）" */
const subtitleStrokeOpacity = 100;
/** @inspect select options="round,miter,bevel" path="繁體字幕/描邊/轉角" */
const subtitleStrokeJoin = "round";
/** @inspect boolean path="繁體字幕/陰影/啟用陰影" */
const subtitleShadowEnabled = true;
/** @inspect color path="繁體字幕/陰影/顏色" */
const subtitleShadowColor = "#000000";
/** @inspect number min=0 max=100 step=1 path="繁體字幕/陰影/不透明度（%）" */
const subtitleShadowOpacity = 77;
/** @inspect number min=0 max=100 step=1 path="繁體字幕/陰影/模糊" */
const subtitleShadowBlur = 0;
/** @inspect number min=0 max=100 step=1 path="繁體字幕/陰影/距離" */
const subtitleShadowDistance = 5;
/** @inspect number min=-180 max=180 step=1 path="繁體字幕/陰影/角度" */
const subtitleShadowAngle = -45;

function Subtitle(props: { id: string; text: string; start: number | string; end: number | string }) {
  return (
    <text id={props.id} name={props.text.replace(/\n/g, " ")} start={props.start} end={props.end} fontFamily={subtitleFont} fontSize={subtitleSize} fontWeight={subtitleWeight} color={subtitleColor} opacity={subtitleOpacity / 100} x={subtitleCentered ? (1440 - subtitleWidth) / 2 : subtitleLeft} y={subtitleTop} width={subtitleWidth} height={subtitleHeight} textAlign={subtitleAlign} textBaseline={subtitleBaseline} leading={subtitleLeading} rotation={subtitleRotation} fontStyle={subtitleFontStyle} letterSpacing={subtitleLetterSpacing} textCase={subtitleTextCase} scaleX={subtitleScaleX} scaleY={subtitleScaleY} offsetX={subtitleOffsetX} offsetY={subtitleOffsetY} keepAspectRatio={subtitleKeepAspect} blendMode={subtitleBlendMode} hidden={!subtitleVisible}>
            {props.text}
            <stroke id={`${props.id}-stroke`} color={subtitleStrokeColor} width={subtitleOutline} join={subtitleStrokeJoin} opacity={subtitleStrokeOpacity / 100} hidden={!subtitleStrokeEnabled} />
            <shadow id={`${props.id}-shadow`} color={subtitleShadowColor} blur={subtitleShadowBlur} offsetX={subtitleShadowDistance * Math.cos(subtitleShadowAngle * Math.PI / 180)} offsetY={-subtitleShadowDistance * Math.sin(subtitleShadowAngle * Math.PI / 180)} opacity={subtitleShadowOpacity / 100} hidden={!subtitleShadowEnabled} />
          </text>
  );
}
