import pygame
import os
import random
import math

# 初始化Pygame
pygame.init()
pygame.font.init()

# 游戏窗口设置
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
TILE_SIZE = 32

# 创建游戏窗口
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Minecraft 2D - 1.01")

# 颜色定义
SKY_COLOR = (135, 206, 235)

# GUI设置
GUI_SCALE = 0.7  # 保持物品栏背景的小尺寸
HOTBAR_IMAGE = pygame.image.load('assets/gui_invrow.png')
HOTBAR_IMAGE = pygame.transform.scale(HOTBAR_IMAGE, 
                                    (int(HOTBAR_IMAGE.get_width() * GUI_SCALE), 
                                     int(HOTBAR_IMAGE.get_height() * GUI_SCALE)))
SLOT_SIZE = int(16 * GUI_SCALE)  # 物品栏格子大小
HOTBAR_PADDING = max(1, int(3 * GUI_SCALE))  # 内边距
HOTBAR_Y_OFFSET = 5  # 添加这个定义

# 物品显示大小和位置调整
ITEM_SCALE = 3.0  # 物品相对于格子的大小比例
ITEM_PADDING = 4  # 水平位置
ITEM_VERTICAL_OFFSET = 4  # 垂直偏移

# 方块类型
BLOCK_TYPES = ["dirt", "grass", "stone", "wood", "leaves", "sand"]

# 加载方块贴图
def load_images():
    images = {}
    for filename in os.listdir("assets"):
        if filename.endswith(".png"):
            name = filename[:-4]  # 移除.png后缀
            images[name] = pygame.image.load(os.path.join("assets", filename)).convert_alpha()
            images[name] = pygame.transform.scale(images[name], (TILE_SIZE, TILE_SIZE))
    return images

class Camera:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.scroll_x = 0
        self.scroll_y = 0
    
    def update(self, player):
        self.scroll_x = player.x - (WINDOW_WIDTH // 2)
        self.scroll_y = player.y - (WINDOW_HEIGHT // 2)
        self.scroll_x = max(0, min(self.scroll_x, self.width - WINDOW_WIDTH))
        self.scroll_y = max(0, min(self.scroll_y, self.height - WINDOW_HEIGHT))

class DroppedItem:
    def __init__(self, x, y, item_type):
        self.x = x
        self.y = y
        self.item_type = item_type
        self.velocity_x = random.uniform(-2, 2)  # 随机水平速度
        self.velocity_y = -4  # 向上的初始速度
        self.gravity = 0.4
        self.size = TILE_SIZE // 2  # 掉落物大小是方块的一半
        self.bobbing = 0  # 用于上下浮动动画
        self.bobbing_speed = 0.1
    
    def update(self, world):
        # 应用重力
        self.velocity_y += self.gravity
        
        # 更新位置
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # 检查与方块的碰撞
        block_x = int(self.x // TILE_SIZE)
        block_y = int((self.y + self.size) // TILE_SIZE)
        
        # 地面碰撞
        if 0 <= block_x < world.width and 0 <= block_y < world.height:
            if world.blocks[block_x][block_y] is not None:
                self.y = block_y * TILE_SIZE - self.size
                self.velocity_y = 0
                self.velocity_x *= 0.8  # 摩擦力
        
        # 浮动动画
        self.bobbing += self.bobbing_speed
        
    def draw(self, screen, camera, block_images):
        # 计算屏幕位置
        screen_x = self.x - camera.scroll_x
        screen_y = self.y - camera.scroll_y + math.sin(self.bobbing) * 3  # 添加上下浮动
        
        if self.item_type in block_images:
            # 缩放物品图像
            scaled_item = pygame.transform.scale(block_images[self.item_type], 
                                              (self.size, self.size))
            screen.blit(scaled_item, (screen_x, screen_y))

class World:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.blocks = [[None for _ in range(height)] for _ in range(width)]
        self.dropped_items = []
        
        # 生成地面
        ground_height = height * 2 // 3  # 地面高度设置在2/3处
        for x in range(width):
            for y in range(ground_height, height):
                self.blocks[x][y] = 'dirt'  # 使用泥土方块作为地面
    
    def generate_terrain(self):
        # 简单的地形生成
        ground_height = self.height // 2
        for x in range(self.width):
            for y in range(self.height):
                if y > ground_height + 3:
                    self.blocks[x][y] = "stone"
                elif y > ground_height:
                    self.blocks[x][y] = "dirt"
                elif y == ground_height:
                    self.blocks[x][y] = "grass"
    
    def place_block(self, x, y, block_type, player):
        if 0 <= x < self.width and 0 <= y < self.height:
            # 检查玩家是否有足够的方块
            if self.blocks[x][y] is None and player.inventory[block_type] > 0:
                self.blocks[x][y] = block_type
                player.inventory[block_type] -= 1
    
    def break_block(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            block_type = self.blocks[x][y]
            if block_type is not None:
                # 生成掉落物
                drop_x = x * TILE_SIZE + TILE_SIZE / 2
                drop_y = y * TILE_SIZE + TILE_SIZE / 2
                self.dropped_items.append(DroppedItem(drop_x, drop_y, block_type))
                # 移除方块
                self.blocks[x][y] = None
    
    def update_items(self, player):
        # 更新掉落物并检查拾取
        items_to_remove = []
        for item in self.dropped_items:
            item.update(self)
            if player.can_pickup(item):
                player.pickup_item(item.item_type)
                items_to_remove.append(item)
        
        # 移除被拾取的物品
        for item in items_to_remove:
            self.dropped_items.remove(item)

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = TILE_SIZE
        self.height = TILE_SIZE * 2
        self.velocity_y = 0
        self.jumping = False
        self.speed = 5
        self.gravity = 0.8
        self.jump_force = -15
        self.selected_block = 0
        self.pickup_range = TILE_SIZE * 1.5  # 拾取范围
        self.inventory = {block_type: 0 for block_type in BLOCK_TYPES}  # 物品栏
    
    def move(self, dx, world):
        new_x = self.x + dx * self.speed
        
        # 检查水平移动碰撞
        if dx > 0:  # 向右移动
            right_tile = int((new_x + self.width) // TILE_SIZE)
            top_tile = int(self.y // TILE_SIZE)
            bottom_tile = int((self.y + self.height - 1) // TILE_SIZE)
            
            can_move = True
            for y in range(top_tile, bottom_tile + 1):
                if 0 <= right_tile < world.width and 0 <= y < world.height:
                    if world.blocks[right_tile][y] is not None:
                        new_x = right_tile * TILE_SIZE - self.width
                        can_move = False
                        break
        
        elif dx < 0:  # 向左移动
            left_tile = int(new_x // TILE_SIZE)
            top_tile = int(self.y // TILE_SIZE)
            bottom_tile = int((self.y + self.height - 1) // TILE_SIZE)
            
            can_move = True
            for y in range(top_tile, bottom_tile + 1):
                if 0 <= left_tile < world.width and 0 <= y < world.height:
                    if world.blocks[left_tile][y] is not None:
                        new_x = (left_tile + 1) * TILE_SIZE
                        can_move = False
                        break
        
        self.x = new_x
        self.x = max(0, min(self.x, world.width * TILE_SIZE - self.width))
    
    def update(self, world):
        # 应用重力
        self.velocity_y += self.gravity
        self.velocity_y = min(self.velocity_y, 15)
        
        # 垂直移动
        new_y = self.y + self.velocity_y
        
        # 检查垂直碰撞
        left_tile = int(self.x // TILE_SIZE)
        right_tile = int((self.x + self.width - 1) // TILE_SIZE)
        
        # 检查碰撞
        if self.velocity_y > 0:  # 下落
            bottom_tile = int((new_y + self.height) // TILE_SIZE)
            for x in range(left_tile, right_tile + 1):
                if 0 <= x < world.width and 0 <= bottom_tile < world.height:
                    if world.blocks[x][bottom_tile] is not None:
                        new_y = bottom_tile * TILE_SIZE - self.height
                        self.velocity_y = 0
                        self.jumping = False
                        break
        elif self.velocity_y < 0:  # 上升
            top_tile = int(new_y // TILE_SIZE)
            for x in range(left_tile, right_tile + 1):
                if 0 <= x < world.width and 0 <= top_tile < world.height:
                    if world.blocks[x][top_tile] is not None:
                        new_y = (top_tile + 1) * TILE_SIZE
                        self.velocity_y = 0
                        break
        
        self.y = new_y
        
        if self.y > world.height * TILE_SIZE:
            self.y = 0
            self.velocity_y = 0
    
    def get_selected_block(self):
        return BLOCK_TYPES[self.selected_block]
    
    def can_pickup(self, item):
        # 计算与掉落物的距离
        dx = item.x + item.size/2 - (self.x + self.width/2)
        dy = item.y + item.size/2 - (self.y + self.height/2)
        distance = math.sqrt(dx * dx + dy * dy)
        return distance < self.pickup_range
    
    def pickup_item(self, item_type):
        self.inventory[item_type] += 1

def main():
    clock = pygame.time.Clock()
    block_images = load_images()
    world = World(100, 100)
    player = Player(WINDOW_WIDTH // 2, 0)
    camera = Camera(100 * TILE_SIZE, 100 * TILE_SIZE)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                world_x = int((mouse_x + camera.scroll_x) // TILE_SIZE)
                world_y = int((mouse_y + camera.scroll_y) // TILE_SIZE)
                
                if event.button == 1:  # 左键破坏方块
                    world.break_block(world_x, world_y)
                elif event.button == 3:  # 右键放置方块
                    world.place_block(world_x, world_y, player.get_selected_block(), player)
            elif event.type == pygame.MOUSEWHEEL:
                player.selected_block = (player.selected_block + event.y) % len(BLOCK_TYPES)
            elif event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]:
                    player.selected_block = event.key - pygame.K_1
        
        # 玩家移动控制
        keys = pygame.key.get_pressed()
        dx = 0
        if keys[pygame.K_a]:
            dx = -1
        if keys[pygame.K_d]:
            dx = 1
        if keys[pygame.K_w] and not player.jumping:
            player.velocity_y = player.jump_force
            player.jumping = True
        
        player.move(dx, world)
        player.update(world)
        camera.update(player)
        
        # 绘制
        screen.fill(SKY_COLOR)
        
        # 绘制世界
        for x in range(world.width):
            screen_x = x * TILE_SIZE - camera.scroll_x
            if -TILE_SIZE <= screen_x <= WINDOW_WIDTH:
                for y in range(world.height):
                    screen_y = y * TILE_SIZE - camera.scroll_y
                    if -TILE_SIZE <= screen_y <= WINDOW_HEIGHT:
                        block = world.blocks[x][y]
                        if block and block in block_images:
                            screen.blit(block_images[block], (screen_x, screen_y))
        
        # 绘制玩家
        pygame.draw.rect(screen, (255, 0, 0), 
                        (player.x - camera.scroll_x, 
                         player.y - camera.scroll_y, 
                         player.width, player.height))
        
        # 绘制物品栏
        hotbar_x = (WINDOW_WIDTH - HOTBAR_IMAGE.get_width()) // 2
        hotbar_y = WINDOW_HEIGHT - HOTBAR_IMAGE.get_height() - HOTBAR_Y_OFFSET
        screen.blit(HOTBAR_IMAGE, (hotbar_x, hotbar_y))
        
        # 绘制物品栏中的方块
        visible_slots = 0  # 跟踪可见的物品槽数量
        for i, block_type in enumerate(BLOCK_TYPES):
            if block_type in block_images and player.inventory[block_type] > 0:  # 只显示拥有的物品
                # 为第一个和第二个物品特别处理
                if visible_slots == 0:
                    slot_x = hotbar_x + HOTBAR_PADDING
                elif visible_slots == 1:
                    # 第二个物品使用更大的间距
                    slot_x = hotbar_x + HOTBAR_PADDING + (int(SLOT_SIZE * 6.0))
                else:
                    # 其他物品使用固定间距
                    slot_x = hotbar_x + HOTBAR_PADDING + (int(SLOT_SIZE * 4.0) * visible_slots)
                
                slot_y = hotbar_y + HOTBAR_PADDING
                
                # 计算物品大小
                item_size = int(SLOT_SIZE * ITEM_SCALE)
                
                # 缩放方块图像
                scaled_block = pygame.transform.scale(block_images[block_type], 
                                                   (item_size, item_size))
                
                # 计算物品位置
                item_x = slot_x + ITEM_PADDING
                item_y = slot_y + ITEM_VERTICAL_OFFSET
                
                # 绘制方块
                screen.blit(scaled_block, (item_x, item_y))
                
                # 绘制物品数量（增大字体）
                count_text = str(player.inventory[block_type])
                font = pygame.font.Font(None, int(SLOT_SIZE * 2))  # 增大字体大小
                text_surface = font.render(count_text, True, (255, 255, 255))
                text_rect = text_surface.get_rect()
                
                # 调整数字位置（右下角，稍微偏移以适应更大的字体）
                text_rect.bottomright = (slot_x + SLOT_SIZE + 4, 
                                       slot_y + SLOT_SIZE + 4)
                
                # 绘制文字阴影
                shadow_surface = font.render(count_text, True, (0, 0, 0))
                screen.blit(shadow_surface, (text_rect.x + 2, text_rect.y + 2))  # 增大阴影偏移
                screen.blit(text_surface, text_rect)
                
                # 绘制选中框
                if i == player.selected_block:
                    pygame.draw.rect(screen, (255, 255, 255), 
                                   (slot_x, slot_y, 
                                    SLOT_SIZE - 1, SLOT_SIZE - 1), 1)
                
                visible_slots += 1  # 增加可见槽位计数
        
        # 更新掉落物和拾取检测
        world.update_items(player)  # 传入 player 参数
        
        # 在绘制玩家之前绘制掉落物
        for item in world.dropped_items:
            item.draw(screen, camera, block_images)
        
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()