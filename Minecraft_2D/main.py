import pygame
import os
import random
import math
from noise import pnoise1
import numpy as np

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
CURSOR_COLOR = (255, 255, 255)  # 白色光标
CURSOR_WIDTH = 2  # 光标线条宽度

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
BLOCK_TYPES = ["dirt", "grass", "rock", "wood", "leaves", "sand", "bedrock", "cobblestone"]

# 定义方块属性
BLOCK_PROPERTIES = {
    "dirt": {"solid": True, "hardness": 10},
    "grass": {"solid": True, "hardness": 10},
    "rock": {"solid": True, "hardness": 500},      # 原石较硬
    "cobblestone": {"solid": True, "hardness": 150},  # 石头
    "wood": {"solid": False, "hardness": 25},
    "leaves": {"solid": False, "hardness": 5},
    "sand": {"solid": True, "hardness": 10},
    "bedrock": {"solid": True, "hardness": float('inf')}  # 基岩无法破坏
}

# 修改掉落物对应关系
BLOCK_DROPS = {
    "dirt": "dirt",
    "grass": "dirt",
    "rock": "cobblestone",    # 原石破坏后掉落石头
    "cobblestone": "cobblestone",
    "wood": "wood",
    "leaves": None,
    "sand": "sand",
    "bedrock": None
}

# 添加挖掘速度常量
MINING_SPEED = {
    "hand": 0.5,  # 空手挖掘速度改为0.5
}

# 加载方块贴图
def load_images():
    images = {}
    for filename in os.listdir("assets"):
        if filename.endswith(".png"):
            name = filename[:-4]  # 移除.png后缀
            image = pygame.image.load(os.path.join("assets", filename)).convert_alpha()
            
            if name == "cursor" or name.startswith("dig"):
                # 获取原始尺寸
                original_width = image.get_width()
                original_height = image.get_height()
                # 缩小到原来的 1/2.5
                new_width = int(original_width / 2.5)
                new_height = int(original_height / 2.5)
                images[name] = pygame.transform.scale(image, (new_width, new_height))
            else:
                images[name] = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
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
        self.block_damage = {}  # 存储方块的当前损坏程度
        self.dropped_items = []
        self.last_damaged_block = None  # 记录最后一次挖掘的方块
        self.current_mining_pos = None  # 添加当前正在挖掘的位置
        self.generate_terrain()
    
    def generate_terrain(self):
        # 地形生成参数
        octaves = 6
        persistence = 0.5
        lacunarity = 2.0
        scale = 50.0
        base_height = self.height * 0.6  # 基准高度在60%处
        
        # 生成地形高度
        heights = []
        for x in range(self.width):
            # 使用柏林噪声生成高度值
            noise_val = pnoise1(x/scale, 
                              octaves=octaves, 
                              persistence=persistence, 
                              lacunarity=lacunarity)
            # 将噪声值转换为实际高度
            height = int(base_height + noise_val * 10)
            heights.append(height)
        
        # 根据高度生成地形
        for x in range(self.width):
            surface_height = heights[x]
            
            # 生成地表
            for y in range(self.height):
                if y >= self.height - 3:  # 最底层3格生成基岩
                    self.blocks[x][y] = "bedrock"
                elif y > surface_height + 5:  # 泥土层下方生成原石
                    self.blocks[x][y] = "rock"  # 这里生成的是原石，破坏后掉落石头
                elif y > surface_height:
                    self.blocks[x][y] = "dirt"
                elif y == surface_height:
                    self.blocks[x][y] = "grass"
                
                # 随机生成沙子
                if y == surface_height and random.random() < 0.1:
                    self.blocks[x][y] = "sand"
        
        # 生成树
        self.generate_trees(heights)
    
    def generate_trees(self, heights):
        for x in range(self.width):
            if random.random() < 0.05:  # 5%的概率生成树
                surface_height = heights[x]
                
                # 确保有足够的空间生成树
                if x < self.width - 2 and surface_height > 5:
                    # 生成树干
                    tree_height = random.randint(4, 6)
                    for y in range(surface_height - 1, surface_height - tree_height - 1, -1):
                        self.blocks[x][y] = "wood"
                    
                    # 生成树叶
                    leaf_radius = random.randint(3, 4)  # 树叶半径
                    leaf_height = random.randint(3, 4)  # 树叶高度
                    
                    # 树叶生成中心点
                    center_y = surface_height - tree_height
                    
                    # 生成树叶
                    for leaf_x in range(x - leaf_radius, x + leaf_radius + 1):
                        for leaf_y in range(center_y - leaf_height, center_y + 1):
                            if (0 <= leaf_x < self.width and 
                                0 <= leaf_y < self.height and 
                                self.blocks[leaf_x][leaf_y] is None):
                                # 计算到中心的距离
                                dx = leaf_x - x
                                dy = leaf_y - center_y
                                distance = math.sqrt(dx * dx + dy * dy)
                                
                                # 只要在半径范围内就生成树叶
                                if distance <= leaf_radius:
                                    self.blocks[leaf_x][leaf_y] = "leaves"
    
    def place_block(self, x, y, block_type, player):
        if 0 <= x < self.width and 0 <= y < self.height:
            # 检查玩家是否有足够的方块
            if self.blocks[x][y] is None and player.inventory[block_type] > 0:
                self.blocks[x][y] = block_type
                player.inventory[block_type] -= 1
    
    def damage_block(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            block = self.blocks[x][y]
            if block is not None:
                # 获取方块的硬度
                hardness = BLOCK_PROPERTIES[block]["hardness"]
                
                # 如果是基岩，直接返回
                if hardness == float('inf'):
                    return
                
                # 创建方块的唯一标识
                block_key = f"{x},{y}"
                
                # 如果挖掘位置改变，重置之前的挖掘进度
                if self.current_mining_pos != block_key:
                    self.reset_block_damage()
                    self.current_mining_pos = block_key
                
                # 初始化方块损坏程度
                if block_key not in self.block_damage:
                    self.block_damage[block_key] = 0
                
                # 增加损坏程度（考虑挖掘速度）
                mining_speed = MINING_SPEED["hand"]  # 目前使用空手挖掘速度
                self.block_damage[block_key] += mining_speed  # 应用挖掘速度
                
                # 如果损坏程度达到硬度，破坏方块
                if self.block_damage[block_key] >= hardness:
                    self.break_block(x, y)
                    self.reset_block_damage()
    
    def reset_block_damage(self):
        """重置所有方块的损坏程度和当前挖掘位置"""
        self.block_damage.clear()
        self.current_mining_pos = None
    
    def break_block(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            block_type = self.blocks[x][y]
            if block_type is not None:
                # 生成掉落物
                drop_type = BLOCK_DROPS.get(block_type)
                if drop_type:
                    drop_x = x * TILE_SIZE + TILE_SIZE / 2
                    drop_y = y * TILE_SIZE + TILE_SIZE / 2
                    self.dropped_items.append(DroppedItem(drop_x, drop_y, drop_type))
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
    
    def draw_block_damage(self, screen, camera, block_images):
        for block_key, damage in self.block_damage.items():
            x, y = map(int, block_key.split(','))
            block = self.blocks[x][y]
            if block:
                hardness = BLOCK_PROPERTIES[block]["hardness"]
                damage_stage = int((damage / hardness) * 10)  # 0-9 的损坏阶段
                
                # 计算屏幕位置
                screen_x = x * TILE_SIZE - camera.scroll_x
                screen_y = y * TILE_SIZE - camera.scroll_y
                
                if (0 <= screen_x <= WINDOW_WIDTH and 
                    0 <= screen_y <= WINDOW_HEIGHT):
                    # 使用对应的挖掘光标图片
                    cursor_name = f"dig{damage_stage + 1}"
                    if cursor_name in block_images:
                        screen.blit(block_images[cursor_name], (screen_x, screen_y))

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
                    block = world.blocks[right_tile][y]
                    if block is not None and BLOCK_PROPERTIES[block]["solid"]:
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
                    block = world.blocks[left_tile][y]
                    if block is not None and BLOCK_PROPERTIES[block]["solid"]:
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
                    block = world.blocks[x][bottom_tile]
                    if block is not None and BLOCK_PROPERTIES[block]["solid"]:
                        new_y = bottom_tile * TILE_SIZE - self.height
                        self.velocity_y = 0
                        self.jumping = False
                        break
        elif self.velocity_y < 0:  # 上升
            top_tile = int(new_y // TILE_SIZE)
            for x in range(left_tile, right_tile + 1):
                if 0 <= x < world.width and 0 <= top_tile < world.height:
                    block = world.blocks[x][top_tile]
                    if block is not None and BLOCK_PROPERTIES[block]["solid"]:
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
    mouse_pressed = False  # 跟踪鼠标按下状态
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键
                    mouse_pressed = True
                elif event.button == 3:  # 右键放置方块
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    world_x = int((mouse_x + camera.scroll_x) // TILE_SIZE)
                    world_y = int((mouse_y + camera.scroll_y) // TILE_SIZE)
                    world.place_block(world_x, world_y, player.get_selected_block(), player)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # 左键释放
                    mouse_pressed = False
                    world.reset_block_damage()  # 重置方块损坏程度
        
        # 如果鼠标左键被按住，继续挖掘
        if mouse_pressed:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x = int((mouse_x + camera.scroll_x) // TILE_SIZE)
            world_y = int((mouse_y + camera.scroll_y) // TILE_SIZE)
            world.damage_block(world_x, world_y)
        
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
        world.update_items(player)
        
        # 在绘制玩家之前绘制掉落物
        for item in world.dropped_items:
            item.draw(screen, camera, block_images)
        
        # 在绘制完方块后绘制损坏效果
        world.draw_block_damage(screen, camera, block_images)
        
        # 获取当前鼠标指向的方块位置
        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x = int((mouse_x + camera.scroll_x) // TILE_SIZE)
        world_y = int((mouse_y + camera.scroll_y) // TILE_SIZE)
        
        # 在所有方块和物品渲染之后，绘制光标
        cursor_screen_x = world_x * TILE_SIZE - camera.scroll_x
        cursor_screen_y = world_y * TILE_SIZE - camera.scroll_y
        
        # 只在没有挖掘进行时显示普通光标
        block_key = f"{world_x},{world_y}"
        if block_key not in world.block_damage and "cursor" in block_images:
            screen.blit(block_images["cursor"], (cursor_screen_x, cursor_screen_y))
        
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()