import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optimizers
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torchvision
import torchvision.transforms as transforms
import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt


class CGAN(nn.Module):
    '''
    Simple Conditional GAN
    '''
    def __init__(self, device='cpu'):
        super().__init__()
        self.device = device
        self.G = Generator(device=device)
        self.D = Discriminator(device=device)

    def forward(self, x, cond):
        x = self.G(x, cond)
        y = self.D(x, cond)

        return y


class Discriminator(nn.Module):
    def __init__(self, device='cpu'):
        super().__init__()
        self.device = device
        self.reshape = lambda x: torch.ones(10, 28, 28).to(device) * x
        self.conv1 = nn.Conv2d(1+10, 128,
                               kernel_size=(3, 3),
                               stride=(2, 2),
                               padding=1)
        self.relu1 = nn.LeakyReLU(0.2)
        self.conv2 = nn.Conv2d(128, 256,
                               kernel_size=(3, 3),
                               stride=(2, 2),
                               padding=1)
        self.bn2 = nn.BatchNorm2d(256)
        self.relu2 = nn.LeakyReLU(0.2)
        self.fc = nn.Linear(256*7*7, 1024)
        self.bn3 = nn.BatchNorm1d(1024)
        self.relu3 = nn.LeakyReLU(0.2)
        self.out = nn.Linear(1024, 1)

        for l in [self.conv1, self.conv2, self.fc, self.out]:
            nn.init.xavier_normal_(l.weight)

    def forward(self, x, cond):
        cond = cond.view(-1, 10, 1, 1)
        cond = self.reshape(cond)
        x = torch.cat((x, cond), dim=1)
        h = self.conv1(x)
        h = self.relu1(h)
        h = self.conv2(h)
        h = self.bn2(h)
        h = self.relu2(h)
        h = h.view(-1, 256*7*7)
        h = self.fc(h)
        h = self.bn3(h)
        h = self.relu3(h)
        h = self.out(h)
        y = torch.sigmoid(h)

        return y


class Generator(nn.Module):
    def __init__(self,
                 input_dim=100,
                 device='cpu'):
        super().__init__()
        self.device = device
        self.linear = nn.Linear(input_dim+10, 256*14*14)
        self.bn1 = nn.BatchNorm1d(256*14*14)
        self.relu1 = nn.ReLU()
        self.conv1 = nn.Conv2d(256, 128,
                               kernel_size=(3, 3),
                               padding=1)
        self.bn2 = nn.BatchNorm2d(128)
        self.relu2 = nn.ReLU()
        self.conv2 = nn.Conv2d(128, 64,
                               kernel_size=(3, 3),
                               padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.relu3 = nn.ReLU()
        self.conv3 = nn.Conv2d(64, 1,
                               kernel_size=(1, 1))

        for l in [self.conv1, self.conv2, self.conv3]:
            nn.init.xavier_normal_(l.weight)

    def forward(self, x, cond):
        x = torch.cat((x, cond), dim=-1)
        h = self.linear(x)
        h = self.bn1(h)
        h = self.relu1(h)
        h = h.view(-1, 256, 14, 14)
        h = nn.functional.interpolate(h, size=(28, 28))
        h = self.conv1(h)
        h = self.bn2(h)
        h = self.relu2(h)
        h = self.conv2(h)
        h = self.bn3(h)
        h = self.relu3(h)
        h = self.conv3(h)
        y = torch.sigmoid(h)

        return y


if __name__ == '__main__':
    np.random.seed(1234)
    torch.manual_seed(1234)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def compute_loss(label, pred):
        return criterion(pred, label)

    def train_step(x, t):
        batch_size = x.size(0)
        model.D.train()
        model.G.train()

        # train D
        # real images
        cond = torch.eye(10)[t.long()].float().to(device)
        preds = model.D(x, cond).squeeze()  # preds with true images
        label = torch.ones(batch_size).float().to(device)
        loss_D_real = compute_loss(label, preds)
        # fake images
        noise = gen_noise(batch_size)
        cond = gen_cond(batch_size).detach()
        z = model.G(noise, cond).detach()
        preds = model.D(z, cond).squeeze()  # preds with fake images
        label = torch.zeros(batch_size).float().to(device)
        loss_D_fake = compute_loss(label, preds)

        loss_D = loss_D_real + loss_D_fake
        optimizer_D.zero_grad()
        loss_D.backward()
        optimizer_D.step()

        # train G
        noise = gen_noise(batch_size)
        cond = gen_cond(batch_size)
        z = model.G(noise, cond)
        preds = model.D(z, cond).squeeze()  # preds with fake images
        label = torch.ones(batch_size).float().to(device)  # label as true
        loss_G = compute_loss(label, preds)
        optimizer_G.zero_grad()
        loss_G.backward()
        optimizer_G.step()

        return loss_D, loss_G

    def generate(cond):
        model.eval()
        batch_size = cond.size(0)
        noise = gen_noise(batch_size)
        gen = model.G(noise, cond)

        return gen

    def gen_noise(batch_size):
        return torch.empty(batch_size, 100).uniform_(0, 1).to(device)

    def gen_cond(batch_size, one_hot=True):
        cond = torch.randint(0, 10, (batch_size,)).long()
        if not one_hot:
            return cond.to(device)
        return torch.eye(10)[cond].float().to(device)

    '''
    Load data
    '''
    root = os.path.join(os.path.dirname(__file__),
                        '..', 'data', 'mnist')
    transform = transforms.Compose([transforms.ToTensor()])
    mnist_train = \
        torchvision.datasets.MNIST(root=root,
                                   download=True,
                                   train=True,
                                   transform=transform)
    train_dataloader = DataLoader(mnist_train,
                                  batch_size=100,
                                  shuffle=True)

    '''
    Build model
    '''
    model = CGAN(device=device).to(device)
    criterion = nn.BCELoss()
    optimizer_D = optimizers.Adam(model.D.parameters(), lr=0.0002)
    optimizer_G = optimizers.Adam(model.G.parameters(), lr=0.0002)

    '''
    Train model
    '''
    epochs = 1000
    out_path = os.path.join(os.path.dirname(__file__),
                            '..', 'output')

    for epoch in range(epochs):
        train_loss_D = 0.
        train_loss_G = 0.
        test_loss = 0.

        for (x, t) in train_dataloader:
            x = x.to(device)
            loss_D, loss_G = train_step(x, t)

            train_loss_D += loss_D.item()
            train_loss_G += loss_G.item()

        train_loss_D /= len(train_dataloader)
        train_loss_G /= len(train_dataloader)

        print('Epoch: {}, D Cost: {:.3f}, G Cost: {:.3f}'.format(
            epoch+1,
            train_loss_D,
            train_loss_G
        ))

        if epoch % 5 == 4 or epoch == epochs - 1:
            cond = torch.eye(10)[torch.arange(10).long()].float().to(device)
            images = generate(cond)
            images = images.squeeze().detach().cpu().numpy()
            plt.figure(figsize=(5, 2))
            for i, image in enumerate(images):
                plt.subplot(2, 5, i+1)
                plt.imshow(image, cmap='binary')
                plt.axis('off')
            plt.tight_layout()
            # plt.show()
            template = '{}/conditional_gan_mnist_epoch_{:0>4}.png'
            plt.savefig(template.format(out_path, epoch+1), dpi=300)
