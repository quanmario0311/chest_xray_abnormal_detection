import torch
from torch._C import dtype
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data.dataloader import DataLoader
import torchvision.transforms as transforms
import random
import os
import numpy as np
from tqdm import tqdm
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from model import ViT
from utils.XrayDataset import ChestXRayDataSet
import numpy as np

seed = 3
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

transform_train = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor()
    ])

transform_val = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.ToTensor()
    ])

transform_test = transforms.Compose([
    transforms.RandomResizedCrop(224), 
    transforms.ToTensor(),
    ])

def read_data(path = ".\chest_xray", mode = 'train'):
    data_path = os.path.join(path,mode)
    if mode == 'train':
        dataset_obj = ChestXRayDataSet(data_path, transform_train)
        dataset = dataset_obj()
    elif mode == 'val':
        dataset_obj = ChestXRayDataSet(data_path, transform_val)
        dataset = dataset_obj()
    else:
        dataset_obj = ChestXRayDataSet(data_path, transform_test)
        dataset = dataset_obj()
    return dataset

def test(model, test_loader, criterion):
    model.to(device)
    test_accuracy = 0
    test_loss = 0
    for data, label in tqdm(test_loader):
        model.eval()
        data = data.to(device)
        label = label.float().to(device)
        output = model(data)
        output = output.float()
        output_size = output.size(0)
        output = output.float().reshape((output_size))
        test_loss = criterion(output, label)

        pred = torch.round(output.detach().cpu())
        target = torch.round(label.detach().cpu())
        acc = (pred == target).sum().float()
        test_accuracy += (acc / output_size) / len(test_loader)
        test_loss += test_loss / len(test_loader)

    print(f"test-loss : {test_loss:.4f} - test-acc: {test_accuracy:.4f}\n")

def train(model, train_loader, valid_loader, criterion, optimizer, scheduler, epochs: int = 100):
    best_val = 100
    model.to(device)
    for epoch in range(epochs):
        epoch_loss = 0
        epoch_accuracy = 0
        for data, label in tqdm(train_loader):
            model.train()
            optimizer.zero_grad()
            #Load data into cuda
            data = data.to(device)
            label = label.float().to(device)
            #Pass data to model
            output = model(data)
            output = output.float()
            output_size = output.size(0)
            output = output.float().reshape((output_size))
            loss = criterion(output, label)
            #Optimizing
            loss.backward()
            optimizer.step()
            #Calculate Accuracy
            pred = torch.round(output.detach().cpu())
            target = torch.round(label.detach().cpu())
            acc = (pred == target).sum().float()
            epoch_accuracy += (acc / output_size) / len(train_loader)
            epoch_loss += loss / len(train_loader)
            if valid_loader is not None:
                epoch_val_accuracy = 0
                epoch_val_loss = 0
                for data, label in valid_loader:
                    model.eval()
                    #Load val_data into cuda
                    data = data.to(device)
                    label = label.float().to(device)
                    #Pass val_data to model
                    val_output = model(data)
                    val_output_size = val_output.size(0)
                    val_output = val_output.float().reshape((val_output_size))
                    
                    val_loss = criterion(val_output, label)
                    #Calculate Validation Accuracy
                    pred = torch.round(val_output.detach().cpu())
                    target = torch.round(label.detach().cpu())

                    val_acc = (pred == target).sum().float()
                    epoch_val_accuracy += (val_acc/val_output_size)/len(valid_loader)
                    epoch_val_loss += val_loss/len(valid_loader)
        # scheduler.step()
        if valid_loader is not None:
            print(
                f"Epoch : {epoch+1} - loss : {epoch_loss:.4f} - acc: {epoch_accuracy:.4f} - val_loss : {epoch_val_loss:.4f} - val_acc: {epoch_val_accuracy:.4f}\n"
                )
            if best_val > epoch_val_loss:
                torch.save(model, 'best-model.pt')
                best_val = epoch_val_loss
                print('saved best')
        else:
            print(
                f"Epoch : {epoch+1} - loss : {epoch_loss:.4f} - acc: {epoch_accuracy:.4f}\n"
                )
        torch.save(model,'last-model.pt')

if __name__ == "__main__":
    #read in data
    default_data_path = "./chest_xray"
    train_data = read_data(default_data_path, 'train')
    val_data = read_data(default_data_path, 'val')
    test_data = read_data(default_data_path, 'test')
    #data loaders
    train_loader = DataLoader(dataset=train_data, batch_size = 256, shuffle=True)
    val_loader = DataLoader(dataset=val_data, batch_size = 16, shuffle=True)
    test_loader = DataLoader(dataset=test_data, batch_size = 16)
    #define model
    vision_transformer = ViT(img_size=224, patch_size=16, num_class=1, d_model=256,n_head=8,n_layers=8,d_mlp=768)
    #configs
    epochs = 300
    criterion = nn.BCELoss()
    criterion.to(device)
    optimizer = optim.AdamW(vision_transformer.parameters())
    scheduler = StepLR(optimizer, step_size=10, gamma=0.1)
    #train
    train(model=vision_transformer, train_loader=train_loader, valid_loader=val_loader, 
        criterion=criterion, optimizer=optimizer, scheduler=scheduler, epochs=epochs)
    last_model = torch.load('last-model.pt')
    best_model = torch.load('best-model.pt')
    print('test_last_model')
    test(last_model, test_loader, criterion)
    print('test_best_model')
    test(best_model, test_loader, criterion)
    