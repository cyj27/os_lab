/*
 * Copyright (c) 2023 Institute of Parallel And Distributed Systems (IPADS),
 * Shanghai Jiao Tong University (SJTU) Licensed under the Mulan PSL v2. You can
 * use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *     http://license.coscl.org.cn/MulanPSL2
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY
 * KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE. See the
 * Mulan PSL v2 for more details.
 */

#include "chcore/container/list.h"
#include <malloc.h>
#include <string.h>
#include "fsm_client_cap.h"
#include <errno.h>

struct list_head fsm_client_cap_table;

/* Return mount_id */
int fsm_set_client_cap(badge_t client_badge, cap_t cap)
{
        /* Lab 5 TODO Begin (Part 1) */
        /* HINT: the fsm_client_cap_node is organized with a linked list which
         * represents a mapping between (client_badge, fs_cap) -> mount_id. You
         * should allocate the node if it's not present or get the
         * fs_client_cap_node. Iterate through the cap_table and place the cap
         * in an empty slot of the cap_table and returns its ordinal.*/
        struct fsm_client_cap_node *node;
        int mount_id = -1;
        for_each_in_list(node, struct fsm_client_cap_node, node, &fsm_client_cap_table) {
                if (node->client_badge == client_badge){
                        if (node->cap_num < 16) {
                                mount_id = node->cap_num;
                                node->cap_table[mount_id] = cap;
                                node->cap_num++;
                }
                        return mount_id;
                }
        }
        node = malloc(sizeof(*node));
        BUG_ON(node == NULL);
        node->client_badge = client_badge;
        node->cap_num = 0;
        memset(node->cap_table, 0, sizeof(node->cap_table));
        list_add(&node->node, &fsm_client_cap_table);
        mount_id = node->cap_num;
        node->cap_table[mount_id] = cap;
        node->cap_num++;
        return mount_id;
        /* Lab 5 TODO End (Part 1) */
}

/* Return mount_id if record exists, otherwise -1 */
int fsm_get_client_cap(badge_t client_badge, cap_t cap)
{
        /* Lab 5 TODO Begin (Part 1) */
        /* HINT: Perform the same behavior as fsm_set_client_cap and gets the
         * cap from the cap_table if it exists. */
        struct fsm_client_cap_node *node;
        int mount_id = -1;
        for_each_in_list(node, struct fsm_client_cap_node, node, &fsm_client_cap_table) {
                if (node->client_badge == client_badge){
                        for (int i = 0; i < node->cap_num; i++) {
                                if (node->cap_table[i] == cap) {
                                        mount_id = i;
                                        return mount_id;
                                }
                        }
                        break;
                }
        }
        return -1;
        /* Lab 5 TODO End (Part 1) */
}
