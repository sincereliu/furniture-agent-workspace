import {mountRoomPage} from "/layout-view/pages/room/index.js";

const pageHost=mountRoomPage(
  JSON.parse(document.getElementById("page-config").textContent),
  JSON.parse(document.getElementById("scene-data").textContent),
);
__PAGE_EXTENSION_SCRIPT__
