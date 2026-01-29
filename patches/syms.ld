__start = 0x80000000;

/* Recomp runtime helper functions - these get recompiled into function calls */
recomp_puts = 0x8F000000;
recomp_exit = 0x8F000004;
recomp_printf = 0x8F000008;

/* OS function wrappers */
osRecvMesg_recomp = 0x8F000010;
osSendMesg_recomp = 0x8F000014;
osCreateMesgQueue_recomp = 0x8F000048;
osViGetCurrentFramebuffer_recomp = 0x8F000058;
osViGetNextFramebuffer_recomp = 0x8F00005C;
osViSwapBuffer_recomp = 0x8F0000B4;
osGetTime_recomp = 0x8F000088;
osInvalICache_recomp = 0x8F000094;
osWritebackDCache_recomp = 0x8F000068;
osWritebackDCacheAll_recomp = 0x8F0000D0;
bzero_recomp = 0x8F0000F0;

/* Controller functions */
osContStartReadData_recomp = 0x8F000070;
osContGetReadData_recomp = 0x8F000074;
osContStartQuery_recomp = 0x8F000078;
osContGetQuery_recomp = 0x8F00007C;

/* EEPROM/Flash save functions */
osEepromRead_recomp = 0x8F000040;
osEepromWrite_recomp = 0x8F000044;
osEepromProbe_recomp = 0x8F0000C0;
osFlashWriteArray_recomp = 0x8F000060;
osFlashWriteBuffer_recomp = 0x8F000064;

/* PI/DMA functions */
osPiStartDma_recomp = 0x8F0000DC;
osCartRomInit_recomp = 0x8F0000C4;
osEPiStartDma_recomp = 0x8F0000C8;

/* Audio */
osAiSetFrequency_recomp = 0x8F0000CC;

/* Thread */
osStartThread_recomp = 0x8F0000E0;

/* Recomp UI/config helpers */
recomp_get_aspect_ratio = 0x8F00001C;
recomp_get_target_framerate = 0x8F000028;
recomp_powf = 0x8F000024;
recomp_time_us = 0x8F000050;
recomp_sleep_miliseconds = 0x8F0000E4;

/* Input helpers */
recomp_get_gyro_deltas = 0x8F000018;
recomp_get_mouse_deltas = 0x8F000080;
recomp_get_camera_inputs = 0x8F00009C;
recomp_get_inverted_axes = 0x8F0000A4;
recomp_get_analog_inverted_axes = 0x8F0000B0;

/* Audio volume helpers */
recomp_get_bgm_volume = 0x8F000030;
recomp_get_sfx_volume = 0x8F0000D4;
recomp_get_env_volume = 0x8F0000D8;

/* NuSystem helpers */
yield_self_1ms = 0x8F0000E8;

/* VI functions for display control */
osViBlack_recomp = 0x8F0000EC;
