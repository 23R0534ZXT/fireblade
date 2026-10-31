using System.Collections;
using System.ComponentModel;
using System.Globalization;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

internal static class Program
{
    static readonly JsonSerializerOptions Json = new() { WriteIndented = false };
    static Assembly Load(string path)
    {
        path = Path.GetFullPath(path);
        var folder = Path.GetDirectoryName(path)!;
        AssemblyLoadContext.Default.Resolving += (_, name) =>
        {
            foreach(var directory in new[]{folder,Path.GetDirectoryName(folder) ?? folder}) {
                var candidate=Path.Combine(directory,name.Name+".dll");
                if(File.Exists(candidate))return AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate);
            }
            return null;
        };
        return AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
    }
    static IEnumerable<Type> Types(Assembly assembly)
    {
        try { return assembly.GetTypes(); }
        catch (ReflectionTypeLoadException e)
        {
            var details=string.Join("; ",e.LoaderExceptions.Select(x=>x?.Message));
            throw new InvalidOperationException("Dépendances du plugin manquantes/incompatibles : "+details,e);
        }
    }
    static Type? ReaderContract(Type type)=>type.GetInterfaces().Append(type).FirstOrDefault(t=>t.GetMethod("ProcessFile",[typeof(string)])!=null && t.GetProperty("DataList")!=null);
    static bool IsReader(Type type) => type.IsClass && !type.IsAbstract && type.GetConstructor(Type.EmptyTypes)!=null && ReaderContract(type)!=null;
    static object Inspect(Assembly assembly) => Types(assembly).Where(IsReader).Select(type =>
    {
        var reader=Activator.CreateInstance(type)!;var contract=ReaderContract(type)!;
        return new {
            type=type.FullName,
            description=contract.GetProperty("FileDescription")?.GetValue(reader)?.ToString() ?? type.Name,
            author=contract.GetProperty("Author")?.GetValue(reader)?.ToString(),
            headers=(contract.GetProperty("ExpectedHeaders")?.GetValue(reader) as IEnumerable)?.Cast<object>().Select(x=>x.ToString()).ToArray()
        };
    }).ToArray();
    static string Cell(object? value) => value switch
    {
        null => "",
        DateTime d => d.ToString("O",CultureInfo.InvariantCulture),
        DateTimeOffset d => d.ToString("O",CultureInfo.InvariantCulture),
        IEnumerable list when value is not string => JsonSerializer.Serialize(value,Json),
        IFormattable f => f.ToString(null,CultureInfo.InvariantCulture) ?? "",
        _ => value.ToString() ?? ""
    };
    static void Record(TextWriter output, IEnumerable<string> cells)
    {
        output.WriteLine(string.Join(",",cells.Select(value=>"\""+value.Replace("\"","\"\"")+"\"")));
    }
    static object ConvertFile(Assembly assembly,string typeName,string source,string target)
    {
        var type=assembly.GetType(typeName,true)!;
        if(!IsReader(type))throw new InvalidOperationException("Type de lecteur TLE invalide");
        var reader=Activator.CreateInstance(type)!;var contract=ReaderContract(type)!;
        // Tag state is kept in Fireblade's analysis; plugins start without tags.
        var tags=contract.GetProperty("TaggedLines");
        if(tags?.CanWrite==true && tags.PropertyType.IsAssignableFrom(typeof(List<int>)))tags.SetValue(reader,new List<int>());
        contract.GetMethod("ProcessFile",[typeof(string)])!.Invoke(reader,[Path.GetFullPath(source)]);
        var data=contract.GetProperty("DataList")!.GetValue(reader) as IEnumerable ?? throw new InvalidOperationException("DataList du plugin n’est pas une collection");
        PropertyDescriptorCollection? columns=null;
        var listType=contract.GetProperty("DataList")!.PropertyType;
        var typed=contract.GetProperty("DataList")!.GetValue(reader) as ITypedList;
        if(typed!=null)columns=typed.GetItemProperties(null);
        if(columns==null || columns.Count==0)
        {
            var generic=data.GetType().GetInterfaces().Append(data.GetType()).FirstOrDefault(t=>t.IsGenericType && t.GetGenericTypeDefinition()==typeof(IList<>));
            if(generic!=null)columns=TypeDescriptor.GetProperties(generic.GetGenericArguments()[0]);
        }
        long count=0;
        using var file=new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None);
        using var output=new StreamWriter(file,new UTF8Encoding(true));
        string[]? names=null;string[]? types=null;
        foreach(var row in data)
        {
            if(row==null)throw new InvalidOperationException("Enregistrement null dans le plugin");
            var dictionary=row as IDictionary<string,object>;
            if(names==null)
            {
                if(dictionary!=null) {names=dictionary.Keys.ToArray();types=names.Select(n=>dictionary[n]?.GetType().FullName ?? "System.String").ToArray();}
                else {
                    if(columns==null || columns.Count==0)columns=TypeDescriptor.GetProperties(row);
                    names=columns.Cast<PropertyDescriptor>().Select(p=>p.Name).ToArray();
                    types=columns.Cast<PropertyDescriptor>().Select(p=>p.PropertyType.FullName ?? "System.String").ToArray();
                }
                if(names.Length==0)throw new InvalidOperationException("Schéma du plugin vide");
                // The native grid owns editable tags. Preserve plugin line IDs as evidence.
                var visible=names.Select(n=>n=="Line"?"TLE_SourceLine":n).Where(n=>n!="Tag");
                Record(output,visible);
            }
            Record(output,names.Where(n=>n!="Tag").Select(n=>Cell(dictionary!=null ? (dictionary.TryGetValue(n,out var field) ? field : null) : columns![n]!.GetValue(row))));count++;
        }
        if(names==null)
        {
            if(columns!=null && columns.Count>0) {names=columns.Cast<PropertyDescriptor>().Select(p=>p.Name).ToArray();types=columns.Cast<PropertyDescriptor>().Select(p=>p.PropertyType.FullName ?? "System.String").ToArray();}
            else if(type.FullName=="TLEFileGenericCsv.GenericCsv") {
                using var text=new StreamReader(source,true);
                string? first=text.ReadLine();if(first?.StartsWith("#TYPE")==true)first=text.ReadLine();
                if(first==null)throw new InvalidOperationException("CSV sans en-tête");
                var delimiter=new[]{',','\t','|',';'}.OrderByDescending(d=>first.Count(c=>c==d)).First();
                using var parser=new Microsoft.VisualBasic.FileIO.TextFieldParser(new StringReader(first));parser.SetDelimiters(delimiter.ToString());parser.HasFieldsEnclosedInQuotes=true;
                names=(parser.ReadFields() ?? []).Where(n=>!string.IsNullOrWhiteSpace(n)).Distinct().Concat(new[]{"Line","Tag"}).ToArray();
                types=names.Select(_=>"System.String").ToArray();
            }
            else throw new InvalidOperationException("Schéma de sortie vide ou inconnu");
            Record(output,names.Where(n=>n!="Tag").Select(n=>n=="Line"?"TLE_SourceLine":n));
        }
        output.Flush();
        return new { rows=count, columns=names.Select((n,i)=>new {name=n=="Line"?"TLE_SourceLine":n,type=types![i],source_name=n}).Where(c=>c.name!="Tag").ToArray() };
    }
    static Dictionary<string,(object instance,MethodInfo method)> Functions(Assembly assembly)
    {
        var result=new Dictionary<string,(object,MethodInfo)>(StringComparer.OrdinalIgnoreCase);
        foreach(var type in Types(assembly).Where(t=>t.IsClass && !t.IsAbstract))
        {
            var contract=type.GetInterfaces().Append(type).FirstOrDefault(t=>t.GetMethod("Evaluate",[typeof(object[])])!=null && t.GetProperty("Name")!=null);
            if(contract==null)continue;
            var instance=Activator.CreateInstance(type)!;
            var name=contract.GetProperty("Name")!.GetValue(instance)?.ToString();
            if(string.IsNullOrWhiteSpace(name))continue;
            if(!result.TryAdd(name,(instance,contract.GetMethod("Evaluate",[typeof(object[])])!)))throw new InvalidOperationException("Nom de fonction dupliqué : "+name);
        }
        return result;
    }
    static string FunctionKind((object instance,MethodInfo method) function)
    {
        try {
            var contract=function.method.DeclaringType!;
            var method=contract.GetMethod("ResultType",[typeof(Type[])]) ?? function.instance.GetType().GetMethod("ResultType",[typeof(Type[])]);
            var type=method?.Invoke(function.instance,[Array.Empty<Type>()]) as Type;
            type=type==null ? null : Nullable.GetUnderlyingType(type) ?? type;
            if(type==typeof(bool))return "boolean";
            if(type==typeof(DateTime) || type==typeof(DateTimeOffset))return "date";
            if(type!=null && new[]{typeof(byte),typeof(short),typeof(int),typeof(long),typeof(ushort),typeof(uint),typeof(ulong),typeof(float),typeof(double),typeof(decimal)}.Contains(type))return "number";
        }catch { }
        return "text";
    }
    static object? Operand(JsonElement value)
    {
        if(value.ValueKind==JsonValueKind.Object && value.TryGetProperty("$fb_type",out var tag))
        {
            var content=value.GetProperty("value");if(content.ValueKind==JsonValueKind.Null)return null;
            var text=content.GetString()!;
            if(tag.GetString() is "date" or "dateoffset")text=System.Text.RegularExpressions.Regex.Replace(text,@"(\.\d{7})\d+","$1");
            return tag.GetString() switch {
                "date" => DateTime.Parse(text,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind),
                "dateoffset" => DateTimeOffset.Parse(text,CultureInfo.InvariantCulture),
                "i64" => long.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u64" => ulong.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "i32" => int.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u32" => uint.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "i16" => short.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u16" => ushort.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u8" => byte.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "decimal" => decimal.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "double" => double.Parse(text,CultureInfo.InvariantCulture),
                "single" => float.Parse(text,CultureInfo.InvariantCulture),
                "bool" => bool.Parse(text),
                _ => throw new InvalidOperationException("Type d’argument .NET inconnu")
            };
        }
        return value.ValueKind switch {
        JsonValueKind.Null => null,
        JsonValueKind.True => true,JsonValueKind.False => false,
        JsonValueKind.String => value.GetString(),
        JsonValueKind.Number => value.TryGetInt64(out var i) ? (object)i : value.TryGetDecimal(out var d) ? (object)d : value.GetDouble(),
        _ => value.Clone()
        };
    }
    static int Serve(Assembly assembly,TextWriter output)
    {
        var functions=Functions(assembly);
        output.WriteLine(JsonSerializer.Serialize(new {ready=true,functions=functions.Keys.ToArray(),types=functions.ToDictionary(p=>p.Key,p=>FunctionKind(p.Value))},Json));output.Flush();
        string? line;
        while((line=Console.ReadLine())!=null)
        {
            try {
                using var request=JsonDocument.Parse(line);var root=request.RootElement;
                var name=root.GetProperty("name").GetString()!;
                if(!functions.TryGetValue(name,out var function))throw new InvalidOperationException("Fonction non chargée : "+name);
                var args=root.GetProperty("arguments").EnumerateArray().Select(Operand).ToArray();
                var value=function.method.Invoke(function.instance,[args]);
                output.WriteLine(JsonSerializer.Serialize(new {value=value is null ? null : value is IEnumerable && value is not string ? JsonSerializer.Serialize(value,Json) : Cell(value)},Json));
            } catch(Exception e) {output.WriteLine(JsonSerializer.Serialize(new {error=(e.InnerException ?? e).Message},Json));}
            output.Flush();
        }
        return 0;
    }
    [STAThread]
    static int Main(string[] args)
    {
        CultureInfo.CurrentCulture=CultureInfo.InvariantCulture;
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        Console.InputEncoding=new UTF8Encoding(false);Console.OutputEncoding=new UTF8Encoding(false);
        try
        {
            if(args.Length==1 && args[0]=="--self-test")
            {
                var folder=Path.Combine(Path.GetTempPath(),"Fireblade host "+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
                try {
                    var source=Path.Combine(folder,"source.txt");File.WriteAllText(source,"évidence\n0001");
                    var info=ConvertFile(Assembly.GetExecutingAssembly(),typeof(QaReader).FullName!,source,Path.Combine(folder,"out.csv"));
                    var text=File.ReadAllText(Path.Combine(folder,"out.csv"));
                    if(!text.Contains("0001") || !text.Contains("évidence"))throw new Exception("Plugin conversion failed");
                    Console.WriteLine(JsonSerializer.Serialize(new {status="passed",result=info},Json));
                } finally {Directory.Delete(folder,true);}
                return 0;
            }
            if(args.Length<2)throw new ArgumentException("inspect DLL | convert DLL TYPE SOURCE TARGET");
            var protocol=Console.Out;
            if(args[0]=="serve")Console.SetOut(Console.Error);
            var assembly=Load(args[1]);
            if(args[0]=="serve")return Serve(assembly,protocol);
            var result=args[0] switch {
                "inspect" when args.Length==2 => Inspect(assembly),
                "functions" when args.Length==2 => Functions(assembly).Keys.ToArray(),
                "convert" when args.Length==5 => ConvertFile(assembly,args[2],args[3],args[4]),
                _ => throw new ArgumentException("Commande de plugin inconnue")
            };
            Console.WriteLine(JsonSerializer.Serialize(result,Json));return 0;
        }
        catch(Exception e) { Console.Error.WriteLine((e is TargetInvocationException ? e.InnerException ?? e : e).ToString());return 1; }
    }
}
// Tiny self-test reader; no investigator data or large CSV generator is used.
public sealed class QaReader
{
    public List<QaRow> DataList { get; } = [];
    public void ProcessFile(string path) { DataList.Add(new QaRow {Text=File.ReadAllText(path),Identifier="0001"}); }
}
public sealed class QaRow { public string Text {get;set;}=""; public string Identifier {get;set;}=""; }

public sealed class QaFunction
{
    public string Name => "QaDouble";
    public object Evaluate(params object[] values) => decimal.Parse(values[0].ToString()!,CultureInfo.InvariantCulture)*2;
}
