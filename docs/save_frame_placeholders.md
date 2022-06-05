#Save frame placeholders
|Placeholder    |Description|Example|
|---------------|-|-|
|{format}       |Pixel format of the frame            |YUV420P10|
|{fps_den}      |FPS denominator                      |1001|
|{fps_num}      |FPS numerator                        |24000|
|{frame}        |Current frame number (zero-indexed)  |55369|
|{height}       |Height of frame in pixels            |960|
|{index}        |Video node number (zero-indexed)     |0|
|{matrix}*      |Matrix coefficients of frame         |BT.709|
|{primaries}*   |Color primaries of frame             |BT.709|
|{range}*       |Color range of frame                 |Limited|
|{script_name}  |Script name without extension        |the-outfit-2022|
|{total_frames} |Number of frames in clip             |151008|
|{transfer}*    |Transfer characteristics of frame    |BT.709|
|{width}        |Width of frame in pixels             |1920|

*currently crashes vspreview when used so example may be malformed
