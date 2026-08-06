# Modelo FLAIR

Esta aplicación utiliza el modelo preentrenado **FLAIR-INC RGB 15 clases — DeepLabV3 + ResNet34** para realizar la segmentación semántica de las imágenes aéreas.

## Descargar los pesos

Los pesos oficiales del modelo se encuentran en Hugging Face:

https://huggingface.co/IGNF/FLAIR-INC_rgb_15cl_resnet34-deeplabv3

Descargar el archivo:

```text
FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth
```

y colocarlo en esta carpeta:

```text
models/
└── FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth
```