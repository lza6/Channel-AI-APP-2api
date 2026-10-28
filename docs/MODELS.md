# 模型清单（上游目录快照）

> 生成时间：2026-10-29T07:22:20　数据源：`/v2/category/newexplore`（匿名接口，无需账号）
> 机器可读版：[`models.json`](../models.json)　验证明细：[`artifacts/bot_verify.json`](../artifacts/bot_verify.json)

**共 278 个模型**：对话（character）260 个 · 绘图（image）18 个 · 分类 17 个

> 说明：上游目录是**动态**的（不同时间拉到的数量会变，实测曾见 187 / 233 / 233），以 `python -X utf8 build_models.py` 现场生成的结果为准。

## 能力字段说明

| 字段 | 含义 | 本项目如何使用 |
|---|---|---|
| `config_type` | `character`=对话角色 / `image`=绘图模型 | 决定走 `/v1/chat/completions` 还是 `/v1/images/generations` |
| `username` | JID localpart（`0_<uuid>`） | **就是 new-api 里的模型名** |
| `can_generate_text` | 可对话 | 对话渠道模型必选 |
| `can_generate_images` | **对话中可顺手出图** | 聊天里它可能回 `🌟 Generating images...` 再给图 |
| `image_generator_jid` | 绑定的绘图模型 | 角色 → 绘图模型的映射 |
| `can_face_swap` | 支持换脸请求 | 未接入 |
| `is_nsfw` / `text_maturity` | 内容分级 | 上游按账号/地区策略过滤 |
| `interactions` | 历史互动数 | **挑选练手模型的指标：越高越稳** |
| `lorebooks` / `suggested_prompts` / `styles` | 角色设定与建议提示词 | 可直接当 prompt 样例 |

## 对话模型 Top 40（按人气）

| 模型名（new-api 用这个） | 显示名 | 互动数 | 能力 | 抽查 | 时延 |
|---|---|---|---|---|---|
| `0_b2cf4ea3-b728-4112-be3d-9829d950bcea` | Stranger | 788964 | text/image | ✅ 已验证 | 5.54s |
| `0_f02210a6-c50c-4ea5-bd92-69296f92f6e0` | Ella | 677337 | text/image | ✅ 已验证 | 13.43s |
| `0_f28ecd20-c129-47b7-8d7e-7fd8a1970bd3` | Tinder Simulator | 452465 | text/image | ✅ 已验证 | 12.79s |
| `0_2f34cb6e-e925-4cc9-a07b-f1b660260b25` | Lyla | 396569 | text/image | ⏳ 未抽查 | — |
| `0_a7591ee3-51a0-48b0-8493-9386556be503` | Leena | 387432 | text/image | ✅ 已验证 | 5.78s |
| `0_e1325059-79b6-4269-93f5-5fc6b01cc26b` | Hailey | 326025 | text/image | ✅ 已验证 | 14.98s |
| `0_e23903e8-89af-46b9-8130-986272d7e9d5` | Agnes | 311649 | text/image | ✅ 已验证 | 12.34s |
| `0_ffeeaf65-583b-4bb0-8026-6e892d66da4f` | Amanda | 297304 | text/image | ⏳ 未抽查 | — |
| `0_d13e0994-3125-4764-ae55-1564d1e1fd60` | Lonely housewife ￼ | 282285 | text/image | ⏳ 未抽查 | — |
| `0_0b2114f1-b757-4012-9836-62e56253f330` | Lucia | 282063 | text/image | ⏳ 未抽查 | — |
| `0_8d0ec215-f313-4cc0-88a5-54e74868e827` | Mia and Emma | 275902 | text/image | ⏳ 未抽查 | — |
| `0_efd25a72-8670-46fb-84b9-7846d9a05f74` | Lily | 272483 | text/image | ⏳ 未抽查 | — |
| `0_2a3734c0-c6f5-4aa9-a104-eaae771e0cd5` | Kim | 256560 | text/image | ⏳ 未抽查 | — |
| `0_96a9c7ce-fc3e-4d4b-bb31-2f0b3ee69918` | Sandy | 256473 | text/image | ⏳ 未抽查 | — |
| `0_d0a545c9-d987-4832-ae59-472bcf9b1fec` | fatima | 255628 | text/image | ⏳ 未抽查 | — |
| `0_1e94730c-69bb-46a9-badb-dd9b4932323b` | Aurora | 225395 | text/image | ⏳ 未抽查 | — |
| `0_ec04f33f-7c40-472f-af70-ac70ab901850` | Michaela | 202400 | text/image | ⏳ 未抽查 | — |
| `0_1b9ba07b-f3be-417a-bbdf-3fea809b889e` | Ms. Martin | 189201 | text/image | ⏳ 未抽查 | — |
| `0_aa16269a-1271-41d0-a7bd-e66ab39f24d6` | Lily | 175365 | text/image | ⏳ 未抽查 | — |
| `0_b75198a6-259e-4aca-a564-342737f4b5cb` | Cassy | 166287 | text/image | ⏳ 未抽查 | — |
| `0_f00627e3-b328-4438-81e3-171ee9722bbb` | Emily | 158267 | text/image | ⏳ 未抽查 | — |
| `0_8b3bb347-5179-4bf7-89f9-ea98836706e8` | Emily | 146217 | text/image | ⏳ 未抽查 | — |
| `0_865de452-4100-4826-824a-1485372596ad` | Ethan | 131977 | text/image | ⏳ 未抽查 | — |
| `0_c037eaf6-d2e3-4efc-a2bc-f9d335c07c05` | Arthur | 121121 | text/image | ⏳ 未抽查 | — |
| `0_f249788a-e4be-4680-b263-c1d43d9f834e` | Alice | 109893 | text/image | ⏳ 未抽查 | — |
| `0_74452dd7-5083-41cb-89df-3bf63d80c70d` | Emily | 101109 | text/image | ⏳ 未抽查 | — |
| `0_9c1d7fc6-286c-414c-afe3-9ea54ef322b6` | Lizzie | 96088 | text/image | ⏳ 未抽查 | — |
| `0_d16b3537-f081-4531-afed-a7bcec57f8e6` | Emily and Sarah | 95760 | text/image | ✅ 已验证 | 11.69s |
| `0_653df635-6cfa-421d-ab13-80903853d106` | Karen | 93732 | text/image | ⏳ 未抽查 | — |
| `0_0354920b-7528-47a5-a369-3a49e5a1f6d8` | Emma | 89784 | text/image | ⏳ 未抽查 | — |
| `0_d6eaef74-5d49-464a-8d5d-a8656548f76e` | Mei | 87281 | text/image | ⏳ 未抽查 | — |
| `0_9a918737-3171-4b19-99fd-028dd62f26dd` | Beach Goth Tomboy | 84971 | text/image | ⏳ 未抽查 | — |
| `0_222bfad6-a9ab-450d-924b-51e0a2c70e20` | Nina Petrov | 82676 | text/image | ⏳ 未抽查 | — |
| `0_ea39861c-e092-4967-9c5c-b7564d1fe114` | Aurora | 77678 | text/image | ⏳ 未抽查 | — |
| `0_07095e84-cdd0-4233-9f6e-4fd1ef98d2d2` | JJ | 77644 | text/image | ⏳ 未抽查 | — |
| `0_2f4faed7-6245-4ad3-b84a-9b275b42adb4` | Emily Wilson | 75587 | text/image | ⏳ 未抽查 | — |
| `0_dc5983b0-3480-4904-adcd-08761c53d6ac` | Maria | 71939 | text/image | ⏳ 未抽查 | — |
| `0_50002887-0fd2-4d6f-8eea-60172dd7ca78` | Zoe | 71091 | text/image | ⏳ 未抽查 | — |
| `0_805f95a6-edbd-4b71-8a83-336fb661df2f` | Ariana, Your Friend's Wife | 70671 | text/image | ⏳ 未抽查 | — |
| `0_899bb17d-e13a-44f2-b967-2d44da223cca` | Lydia | 70487 | text/image | ⏳ 未抽查 | — |

## 绘图模型（全部 18 个）

| 模型名（new-api 用这个） | 显示名 | 互动数 | 能力 | 抽查 | 时延 |
|---|---|---|---|---|---|
| `0_febd3c8d-a862-4d0b-ab5e-7438c26f7aea` | Real Amateur Photos | 5886820 | image | ⏳ 未抽查 | — |
| `0_d9146221-91c1-440c-9334-d71a999c5350` | Z-image | 911993 | image | ⏳ 未抽查 | — |
| `0_05d35190-fb62-450d-8665-26f5092d5c6e` | Cyberrealistic Pony | 808019 | image | ⏳ 未抽查 | — |
| `0_219d7746-9534-417a-ac41-8b0cb65c1064` | Z-image Amateur | 769923 | image | ⏳ 未抽查 | — |
| `0_c936d631-f909-460a-8e7f-48f54bf2e04f` | WAI Anime Ultra | 677900 | image | ⏳ 未抽查 | — |
| `0_8277055a-7828-4bf2-bc94-381d62bb9282` | Character 4 - Realistic Inst | 211094 | image | ⏳ 未抽查 | — |
| `0_9fd53533-a2b4-44b5-b07a-15f0c212709b` | Realistic Skin & Face - Beau | 131524 | image | ⏳ 未抽查 | — |
| `0_8305d2cc-a21a-4632-b251-9ea0a174c0e8` | Tan Girls | 131488 | image | ⏳ 未抽查 | — |
| `0_27c09e0f-9bd2-4e9d-ba81-f87189994b06` | Illustrious Monochrome Manga | 86242 | image | ⏳ 未抽查 | — |
| `0_bc98630a-dff4-4a1a-a152-098b4fe41bf0` | Asura Style [IL] | 54229 | image | ⏳ 未抽查 | — |
| `0_cc395679-4bba-4677-bc9a-aed42855ebf9` | Prefect Illustrious XL | 42552 | image | ⏳ 未抽查 | — |
| `0_f9e873e7-5825-4a65-bb3d-d5c9dc4d0d97` | Channel Rouge 1.0 | 35528 | image | ⏳ 未抽查 | — |
| `0_0f487ca2-69fd-47af-b54c-007dee93a723` | Channel Snap 1.0 | 31878 | image | ⏳ 未抽查 | — |
| `0_1cafcaf3-f32b-4d50-90c3-954b89a30c55` | MGE Monster Girls | 30611 | image | ⏳ 未抽查 | — |
| `0_e4e4174d-60cc-4b47-84d8-34cbe46ad2b0` | Dreikoo style | Goofy Ai | 28964 | image | ⏳ 未抽查 | — |
| `0_4ac1fa22-3a51-4f41-a4b1-353324c697b6` | SameFace Fix [Flux Lora] | 19542 | image | ⏳ 未抽查 | — |
| `0_2d61b38e-26e2-41bc-a453-c2640116285b` | Classic + (Neo) Film Noir Ci | 4709 | image | ⏳ 未抽查 | — |
| `0_3953e022-dc19-4fd9-b20c-3a82ba43c6dc` | Dandonfuga Style | 4647 | image | ⏳ 未抽查 | — |

## 全部模型名（直接粘进 new-api 渠道「模型」框）

```
0_b2cf4ea3-b728-4112-be3d-9829d950bcea
0_f02210a6-c50c-4ea5-bd92-69296f92f6e0
0_f28ecd20-c129-47b7-8d7e-7fd8a1970bd3
0_2f34cb6e-e925-4cc9-a07b-f1b660260b25
0_a7591ee3-51a0-48b0-8493-9386556be503
0_e1325059-79b6-4269-93f5-5fc6b01cc26b
0_e23903e8-89af-46b9-8130-986272d7e9d5
0_ffeeaf65-583b-4bb0-8026-6e892d66da4f
0_d13e0994-3125-4764-ae55-1564d1e1fd60
0_0b2114f1-b757-4012-9836-62e56253f330
0_8d0ec215-f313-4cc0-88a5-54e74868e827
0_efd25a72-8670-46fb-84b9-7846d9a05f74
0_2a3734c0-c6f5-4aa9-a104-eaae771e0cd5
0_96a9c7ce-fc3e-4d4b-bb31-2f0b3ee69918
0_d0a545c9-d987-4832-ae59-472bcf9b1fec
0_1e94730c-69bb-46a9-badb-dd9b4932323b
0_ec04f33f-7c40-472f-af70-ac70ab901850
0_1b9ba07b-f3be-417a-bbdf-3fea809b889e
0_aa16269a-1271-41d0-a7bd-e66ab39f24d6
0_b75198a6-259e-4aca-a564-342737f4b5cb
0_f00627e3-b328-4438-81e3-171ee9722bbb
0_8b3bb347-5179-4bf7-89f9-ea98836706e8
0_865de452-4100-4826-824a-1485372596ad
0_c037eaf6-d2e3-4efc-a2bc-f9d335c07c05
0_f249788a-e4be-4680-b263-c1d43d9f834e
0_74452dd7-5083-41cb-89df-3bf63d80c70d
0_9c1d7fc6-286c-414c-afe3-9ea54ef322b6
0_d16b3537-f081-4531-afed-a7bcec57f8e6
0_653df635-6cfa-421d-ab13-80903853d106
0_0354920b-7528-47a5-a369-3a49e5a1f6d8
0_d6eaef74-5d49-464a-8d5d-a8656548f76e
0_9a918737-3171-4b19-99fd-028dd62f26dd
0_222bfad6-a9ab-450d-924b-51e0a2c70e20
0_ea39861c-e092-4967-9c5c-b7564d1fe114
0_07095e84-cdd0-4233-9f6e-4fd1ef98d2d2
0_2f4faed7-6245-4ad3-b84a-9b275b42adb4
0_dc5983b0-3480-4904-adcd-08761c53d6ac
0_50002887-0fd2-4d6f-8eea-60172dd7ca78
0_805f95a6-edbd-4b71-8a83-336fb661df2f
0_899bb17d-e13a-44f2-b967-2d44da223cca
0_3b6370e6-1a68-4236-aa98-40b5809e4a7a
0_b9259228-f15c-4a92-bd96-31ebe51b72da
0_3f53c8e5-5330-44f1-be63-bf3b45ca8f94
0_bfc0cb2d-8db8-4908-a683-f62cec80467c
0_c2d973ff-7d03-4805-b8a6-546a2b26f898
0_e00dfc19-b3c9-4be8-aae1-0144c16dc204
0_7d9129d7-02fa-4ab6-9fc9-590dbbffa48d
0_05b97b15-7f9d-4035-8571-6ae17af2e602
0_ee1fbcf2-7424-4303-8295-78286864ab3c
0_6422ca41-29ab-46ee-951d-b19180ad4f55
0_d09d8ad5-5c43-4411-8408-acc6086e7f23
0_b6d7972d-3728-4bdb-9e8b-3d3a9261a7fd
0_a6f9befd-bda9-4609-9f14-139831fd8a46
0_549673ee-4ade-4815-955b-eb8a22782302
0_ba57f819-b509-4db4-be4d-38938d848475
0_cf99220a-4b14-435b-a203-63a98f84bf07
0_ec6820ab-25a2-4635-a325-db415286b3ed
0_5f2323c3-4125-4bab-80dd-9615d60f4371
0_7566b085-bfdd-48a5-a63b-a6c7b4925646
0_f5989298-3ffb-4717-860b-e0b6749e1d20
0_571955f8-782d-420b-9cd8-9f16811a1640
0_57dbff23-f34b-4744-8246-303a94d0bc7b
0_39d283e4-c02b-41b2-b5d8-47a4d7c57169
0_f6ea0d07-672b-42d9-b345-dd7b93760261
0_9120eb52-1681-4914-a497-4203a73daf5f
0_da8a41c5-485f-478d-a1ee-356fc7c830a5
0_d80eddfc-ee24-443d-8fb8-19f68cf6d341
0_6ab1b923-94c2-4000-b648-06458d8e4380
0_383d943e-5a49-4d4a-96e6-8620ec0e9a78
0_ef6ebb8c-7865-4dc2-aa8b-68778894c759
0_115e3aa2-22ad-43cb-baba-fcb615d51249
0_fa7fae56-d278-480c-a9c5-c8d64bdb1028
0_5a222b83-9554-4bb8-86de-5b36922f3e5a
0_83d8360a-b342-4811-b9de-8f890310e77f
0_73513ebe-b7ec-4b2f-ab4e-bbc0029b17b9
0_15c7ccf3-f6cc-4954-bd76-6d52bb76c9c5
0_85422b33-e0cf-4b68-a873-1cbea49f3faf
0_ca489aae-42c3-4f29-a21e-8bbb7ff7838c
0_4d9f787e-7104-4103-bc22-b1144277d105
0_98699008-cf44-418a-8b7e-9605c0c73c19
0_d2dca928-c99f-4b2a-af1c-d5e662c64c40
0_5600e199-e027-4eb5-9899-db3fc1fe15f7
0_54254960-28a5-4cd3-822e-89e47fd2edd5
0_0df2ccf9-bb8e-4a0c-9b1e-fb24c8db9b67
0_5c91935f-df90-4c69-be63-6bf239476730
0_f8aaa9f4-7e72-4629-84e4-d54d800411d5
0_edfe68e4-ea10-44d7-8b87-6e3cebd0dd72
0_a6e0dd82-2d3a-467a-90d4-2c746e121c47
0_0e039fb6-3730-49e2-92ea-4ec2a1077388
0_2f36fa62-9a76-41dc-b571-3420854c4f46
0_9dd2387e-8f78-49c9-8d68-1469d70610f4
0_4488193e-c30f-4225-ac4a-49f956708fe9
0_8b652ac7-f1a3-452e-8d23-51bb235e787a
0_5ad1c649-7ee0-4407-bc31-808a0de1054f
0_70d0f4ab-c440-4d2d-bc1b-6fdcf76f4031
0_59ccfc26-9ca4-442a-9b64-bc0f0ea50492
0_a7dd9c33-9632-4d5e-8e88-c0bd91ed13c8
0_a06f0b16-5964-49d7-bf37-19094aae0ed5
0_b3fd6d00-8b9a-42bc-bd1d-d9ecb46850bd
0_2c408afa-8558-453f-8963-916bf85e8fe2
0_5c2b8c03-9b06-456e-92e1-63f7fb57576a
0_49eef3e9-647f-46cf-9e57-6ec2889f584e
0_9702629b-a061-4e8f-8cd5-7bdf038d713a
0_5c036922-2f21-4283-a499-07880b4cbcc3
0_b5452bef-03b9-4953-adc2-33b76988f4d8
0_50bbeb5c-dea3-4fd7-b1ab-5693a79ece77
0_e5590062-311e-45e1-84f3-f8a35809a93b
0_a0f562eb-fb86-4c04-92cf-41d165cee4fc
0_99171cac-afc9-4dcf-8bb4-fdbe77c797a2
0_8d221de4-7191-4a99-ab10-066c0b9982d7
0_271fda9e-0edf-438a-a3f8-386f4d1d8be5
0_66d3ee30-e420-4c4c-818c-9880533a1267
0_e9eba19f-6617-46b8-8f45-7c8a12a7e1ce
0_a7be8ff8-25d1-4ca0-8a51-41ac32171de0
0_195fd0ec-5026-4c3c-a562-c032e4880a43
0_85bedf25-42e3-4ac9-ac19-7bd05a48057a
0_01d34dd7-16cd-4306-86ca-ee840b586b1b
0_4398ee30-a0ad-41eb-95bb-071ff0438a67
0_38eb4327-0a20-4b5a-ac39-9b7b76680f69
0_ea69e132-e4c3-4d5e-a24f-096746af31d2
0_ef243185-8d31-46bf-84e5-2913422ebe92
0_b2a1d83a-ff92-43b2-9d70-0d5a9db0aeef
0_f3ed74dd-842a-4ef5-b6d6-057043b32393
0_c75bfc69-9080-48c8-9e84-8e33f3a5b7eb
0_4e534782-78d4-4a0f-aa4c-0653e8a0bb21
0_a2ffe55b-04c7-489f-b3ae-55ca125e5a28
0_995e9b36-b717-456e-91ef-e85b105ce62f
0_5ea988cd-43a3-4ee2-81f4-79dd433dac51
0_b096689b-8871-49d2-a322-fc6eb0779e2a
0_55feb773-1147-4ee1-b475-0dd1a808eea8
0_c9592dd2-4afb-457a-b544-eb0ff10c714c
0_377d9b4f-4b1b-4835-968c-4e5638a07f9f
0_884f895e-87c7-4a48-a896-9e202bb8eb55
0_ed9feba5-56dd-4ef4-aa31-af71d8fafc60
0_0653c2d9-75b8-4e46-8c10-9eb90d6de393
0_7047e1d9-5844-4d0e-bb0e-0fa6bb2fc39a
0_e17b2331-d067-452c-9d2c-b796a4f9b227
0_74755c5d-d07c-41e4-b9fc-1b0135186e0d
0_af657426-f9e2-4ca7-884b-1213966c5db1
0_7923efe3-b1a8-4cde-9d34-18e240bce66c
0_56e362e4-13bb-4d32-a9d0-a45b1437c5eb
0_5f7cc50d-1237-4973-b46a-041a6893caec
0_a4b8bdf1-bfaa-4cc7-9d50-f23bce98c4ee
0_7858de25-f72c-4647-8d2d-aeab17eb8bc5
0_f9592d55-74ec-4183-a3c2-26d9c7023c7e
0_d8d3935d-82e7-4c58-8ccd-c62f5dc00d41
0_5505a73f-250d-4047-aeef-dad64821645c
0_5e6ce899-159d-4597-9c51-446c84d8e2bf
0_79c14e53-ead7-4210-838f-7a644dd34d43
0_8c2d3164-df9d-406d-a377-1b13d08591b2
0_5821438a-dfa6-481b-8926-49fad6e6d67a
0_a196344e-5235-44bf-a9bf-71424b9b1197
0_365f8871-90e0-44fa-9198-38750d7bdfd5
0_54d86ae6-44fa-43f1-8a97-c289f85dbeb9
0_d6677e71-6c1a-40c3-a07a-8e448c5d5271
0_964fa9ea-55b9-47e3-9c7d-00e98e03828a
0_0e2ef87c-7666-44a8-b6e2-1fdf1e0a63c2
0_96cba1c3-a593-4b9b-b8ae-998ef65d7422
0_9fa94565-93f6-48c9-9cfb-aa57b3a1fb72
0_baf669a3-089b-42cf-844a-54e2ac15313b
0_06023428-03c5-49cf-88fc-62a76dd0220a
0_6ed9cff8-cbae-4187-ab7e-23ba5ef9219e
0_747b0bf1-22ab-4ecb-8713-a852057f9f8e
0_4ef5c74d-43de-4490-aa7c-ac632d6f5f84
0_aeb4ca65-7171-4dee-8491-820258459637
0_7f3e3a9a-cee5-4022-9b0a-fb9de55aed1c
0_59c3bcc7-5cbc-43bc-9e8c-cecea2bb248e
0_ec0c6f2e-168d-437c-a063-d4437fe59975
0_9d7f996d-941e-4df3-8fb5-96f26a7f61e3
0_9ba67543-36d8-4dbb-8fd6-e89ed27ef2d2
0_43ed3634-5144-4ca7-a76c-1c2d46fe0c58
0_7b864c5b-e3e9-4352-9ad9-f9312dbc7098
0_bfb7e70b-4796-43e7-bffc-bcdba7f452d7
0_a12db468-333f-4fa2-b849-55c20ca54ff4
0_1b9ec035-fbc4-4172-8bcf-c78ac6bbe399
0_7443473d-4a44-4f38-9bd6-240d14e52205
0_b77f2add-5fd5-48f9-9fe4-a1092c2a379a
0_5656b536-902a-4763-8ad3-d0fc7dd4448d
0_06308839-e722-4611-9d8b-8ad8c195ee99
0_e9f85d5f-75a7-40e6-9a7f-6c4002062e8b
0_7ac1c15a-454d-4575-b96d-e80e7d6c162c
0_8082d399-db88-425a-a0fb-5468485afab2
0_4e9e81b1-a04f-4c2b-89c3-1489c71ac4b9
0_96476c09-1e5a-41da-90c1-cb2275e7820d
0_789e35ad-c3b2-427f-98a8-b998a897d319
0_920d3de8-4c40-447c-b1ee-7a6241372bd0
0_0a338c6b-f711-47ec-a9e5-2af4eefaa4e9
0_e5a337fe-8c96-49ee-a413-e50c32e2c6a8
0_07d40619-b662-4028-bcc2-a185491c0a04
0_4f9f19e7-93ef-4c8a-b953-733c68939dc9
0_5f0aaaa5-f82e-443e-99b6-6e3a0a2e2244
0_6eab1f8d-1f54-443a-9cfb-ebacba2fe3cd
0_0718342c-f75c-4ceb-9661-fbb45ba1b551
0_2d9d33d4-3423-478e-9bce-a416036fb205
0_a2fb37eb-25a0-4b3a-bac1-8cb4a5489001
0_2bfe4b91-5fb3-4942-8e04-c8853ae81142
0_261b81a7-eb5f-4526-b8fb-c0909c9990c6
0_dc3ff21a-4fa8-4c6a-8219-11d22caf6218
0_577b384e-49b1-4226-b9b9-3e04bb932b4b
0_2100da69-9d09-4ea1-8509-3e8efad0a944
0_cf161810-f6c7-4ed1-b387-52acffdc5e49
0_6f7a3fac-f8ec-497f-ba00-16f55ce81c0e
0_4c145555-8274-449e-b5a9-8a75c7cde570
0_97cd550e-acc0-406f-893b-06c9b0b6de8c
0_4cf75b21-ddbd-47ad-a0e9-205c2aec5a99
0_ee96302b-4522-45e8-b562-f2fafe6a3d06
0_ac2590a6-d1bb-47fb-9603-548aea565a73
0_89ca0886-a5a3-49c6-8b08-ba0a933eeaa8
0_ecd7484d-df85-4ff7-bae1-a13a6c08068a
0_03f205d3-4ec4-4fee-9617-9e81ae5d382c
0_e573b436-bef0-4649-a6e7-9cc9c6a5a7dd
0_69721963-832a-4e37-9c77-adee19b4604a
0_8e8737d0-f019-4dfd-b9f2-6cf686633326
0_89354e14-6e8f-4e18-955c-12e3168e049d
0_d40fc134-d45e-48b0-9e61-7b6698191605
0_e636be8e-ad25-41d9-bb15-e9c54ebf3228
0_e3093c9d-17da-4791-b0e9-7a750d92978b
0_e788650f-a785-4352-9e90-9b9d4fc49705
0_86c9209f-1310-43dc-abe3-ed92862eefc3
0_d4018f05-17db-480f-a2ac-ac43edf536b1
0_c60284be-d54c-4238-ac18-edaec2e3a9b6
0_a7d7d947-932f-405f-be28-aaa1c5930b4a
0_2def9931-a540-49f5-a83b-caa38eb3ab3b
0_1307a715-79ba-4c28-8739-bce780e9b07f
0_b50cc67f-715c-4a83-8c51-80d7aa79118a
0_dd6b22f2-7e12-4b23-878c-ff3cc7060ac1
0_5a31f549-2779-417b-a14b-73bd2005b3be
0_ae0061d0-4f1b-4d48-a4f3-cce11211ef6f
0_8d7f83c8-63af-41a6-b4f5-b7d82cca3c83
0_a5e7eae9-c435-45ee-81eb-fa9dc3ac21d1
0_19ed43e9-2c9d-43ec-978c-0198c87855b8
0_998a5207-9d02-41a7-8913-0b8639a04e41
0_9ee727d2-7928-444f-a0d1-f1be33530bc1
0_7007eddd-b738-4849-be5c-0b67c6a62975
0_ae79fd6e-d1fc-4762-bffe-699ab6fc0084
0_de7622ca-8e21-49f9-95ef-aea255e39289
0_a05ce5e1-563e-430c-b88a-5eee98458f5c
0_4b73d1fd-ee2a-4802-8606-4881f1137872
0_7a312a19-beb4-4fe5-9fc7-597c3b854181
0_2e0c40e5-42ad-4c35-be78-0e654044ab38
0_822a01a1-8e97-42fc-be90-f3a8ae67c75a
0_f3e9a46d-3585-4f43-9233-8ece36bc1f91
0_73250c4b-aab7-472d-a91f-6658285c853d
0_0a730d3e-fbee-4932-95a3-1e32d9a25e66
0_2b0fbffe-05e9-4501-a337-57212df31e85
0_86b38017-fb84-431a-9e3d-91f964f5c7fe
0_53dcbe03-6c4c-4f06-b474-ef5089bb14c3
0_9050db2d-1706-4729-80e8-3aab099a5db2
0_94dfaddc-8eb3-4e04-bb84-46c7a1dcafef
0_297d647f-0569-450d-bdf1-6bc409d41677
0_2572a27c-465e-4e15-bff0-3173c99f9655
0_a3eea898-0375-4d74-aa51-5b2193d83439
0_27faafa6-c954-4a0a-8920-b380429707cd
0_755badb1-712e-4c2f-b8a0-3c34a80f7e35
0_d85fd5f2-c043-43cb-9b04-ec0a4e86dfc3
0_82d60527-5006-4426-9d6a-aa90afb2bed2
0_5f943adf-9475-4999-8f64-362dcf2644fd
0_7003984d-7c00-4135-b7f2-580d94c8923c
0_d306d72c-f358-495d-90d3-64d6b24f736d
0_7cbdc5e0-f1aa-4103-aea0-8ab5c8e3d4a9
0_febd3c8d-a862-4d0b-ab5e-7438c26f7aea
0_d9146221-91c1-440c-9334-d71a999c5350
0_05d35190-fb62-450d-8665-26f5092d5c6e
0_219d7746-9534-417a-ac41-8b0cb65c1064
0_c936d631-f909-460a-8e7f-48f54bf2e04f
0_8277055a-7828-4bf2-bc94-381d62bb9282
0_9fd53533-a2b4-44b5-b07a-15f0c212709b
0_8305d2cc-a21a-4632-b251-9ea0a174c0e8
0_27c09e0f-9bd2-4e9d-ba81-f87189994b06
0_bc98630a-dff4-4a1a-a152-098b4fe41bf0
0_cc395679-4bba-4677-bc9a-aed42855ebf9
0_f9e873e7-5825-4a65-bb3d-d5c9dc4d0d97
0_0f487ca2-69fd-47af-b54c-007dee93a723
0_1cafcaf3-f32b-4d50-90c3-954b89a30c55
0_e4e4174d-60cc-4b47-84d8-34cbe46ad2b0
0_4ac1fa22-3a51-4f41-a4b1-353324c697b6
0_2d61b38e-26e2-41bc-a453-c2640116285b
0_3953e022-dc19-4fd9-b20c-3a82ba43c6dc
```

## 想只看一小批？

```bash
# 导出全部模型名（每行一个，直接粘进 new-api 渠道的模型框）
python -c "import json;print('
'.join(m['id'] for m in json.load(open('models.json'))['models']))"

# 只要绘图模型
python -c "import json;print('
'.join(m['id'] for m in json.load(open('models.json'))['models'] if m['type']=='image'))"

# 人气前 10 的对话模型
python -c "import json;d=[m for m in json.load(open('models.json'))['models'] if m['type']=='character'];d.sort(key=lambda m:-(m['interactions'] or 0));print('
'.join(m['id'] for m in d[:10]))"
```

## 抽查结果（`verify_bots.py`）

最近一次抽查：**25/25 个对话模型可用**（详见 `artifacts/bot_verify.json`；抽查只覆盖样本，不代表未抽查的不可用）。
