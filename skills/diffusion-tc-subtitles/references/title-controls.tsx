// Optional opening-title style. Copy into the composition that uses it.
// Reference canvas: 1080 × 1920. Set wording and timing for the current video.
/** @inspect font path="片頭標題/字型" */
const titleFont = "Noto Sans TC";
/** @inspect number min=12 max=240 step=1 path="片頭標題/字級" */
const titleSize = 108;
/** @inspect number min=100 max=900 step=100 path="片頭標題/字重" */
const titleWeight = 800;
/** @inspect select options="normal,italic,oblique" path="片頭標題/字體樣式" */
const titleFontStyle = "normal";
/** @inspect color path="片頭標題/顏色" */
const titleColor = "#F7F7F7";
/** @inspect number min=0 max=100 step=1 path="片頭標題/不透明度（%）" */
const titleOpacity = 97;
/** @inspect number min=-1080 max=2160 step=1 path="片頭標題/X" */
const titleX = 121;
/** @inspect number min=-1920 max=3840 step=1 path="片頭標題/Y" */
const titleY = 251;
/** @inspect number min=1 max=2160 step=1 path="片頭標題/寬度" */
const titleWidth = 900;
/** @inspect number min=1 max=3840 step=1 path="片頭標題/高度" */
const titleHeight = 320;
/** @inspect select options="left,center,right" path="片頭標題/水平對齊" */
const titleAlign = "center";
/** @inspect select options="top,middle,bottom" path="片頭標題/垂直對齊" */
const titleBaseline = "top";
/** @inspect number min=0.5 max=3 step=0.05 path="片頭標題/行距" */
const titleLeading = 1.1;
/** @inspect number min=-20 max=50 step=0.5 path="片頭標題/字距" */
const titleLetterSpacing = 0;
/** @inspect boolean path="片頭標題/描邊/啟用" */
const titleStrokeEnabled = true;
/** @inspect color path="片頭標題/描邊/顏色" */
const titleStrokeColor = "#787878";
/** @inspect number min=0 max=30 step=0.5 path="片頭標題/描邊/寬度" */
const titleStrokeWidth = 6;
/** @inspect select options="round,miter,bevel" path="片頭標題/描邊/轉角" */
const titleStrokeJoin = "round";
/** @inspect number min=0 max=100 step=1 path="片頭標題/描邊/不透明度（%）" */
const titleStrokeOpacity = 78;
/** @inspect boolean path="片頭標題/陰影/啟用" */
const titleShadowEnabled = true;
/** @inspect color path="片頭標題/陰影/顏色" */
const titleShadowColor = "#000000";
/** @inspect number min=0 max=100 step=1 path="片頭標題/陰影/不透明度（%）" */
const titleShadowOpacity = 45;
/** @inspect number min=0 max=100 step=1 path="片頭標題/陰影/模糊" */
const titleShadowBlur = 10;
/** @inspect number min=-100 max=100 step=0.5 path="片頭標題/陰影/水平偏移" */
const titleShadowX = 1.5;
/** @inspect number min=-100 max=100 step=0.5 path="片頭標題/陰影/垂直偏移" */
const titleShadowY = 3;

function OpeningTitle(props: { id: string; text: string; start: number | string; end: number | string }) {
  return (
    <text id={props.id} name={props.text.replace(/\n/g, " ")} start={props.start} end={props.end} fontFamily={titleFont} fontSize={titleSize} fontWeight={titleWeight} fontStyle={titleFontStyle} color={titleColor} opacity={titleOpacity / 100} x={titleX} y={titleY} width={titleWidth} height={titleHeight} textAlign={titleAlign} textBaseline={titleBaseline} leading={titleLeading} letterSpacing={titleLetterSpacing}>
      {props.text}
      <stroke id={`${props.id}-stroke`} color={titleStrokeColor} width={titleStrokeWidth} join={titleStrokeJoin} opacity={titleStrokeOpacity / 100} hidden={!titleStrokeEnabled} />
      <shadow id={`${props.id}-shadow`} color={titleShadowColor} blur={titleShadowBlur} offsetX={titleShadowX} offsetY={titleShadowY} opacity={titleShadowOpacity / 100} hidden={!titleShadowEnabled} />
    </text>
  );
}
